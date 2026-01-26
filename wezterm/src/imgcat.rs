//! CX Terminal: Image display command (imgcat)
//!
//! Output images to the terminal using iTerm2 inline image protocol.

use anyhow::{anyhow, Context};
use clap::builder::ValueParser;
use clap::{Parser, ValueEnum, ValueHint};
use std::ffi::OsString;
use std::io::Read;
use termwiz::caps::Capabilities;
use termwiz::escape::esc::{Esc, EscCode};
use termwiz::escape::osc::{ITermDimension, ITermFileData, ITermProprietary, OperatingSystemCommand};
use termwiz::escape::OneBased;
use termwiz::input::{InputEvent, KeyCode, KeyEvent, Modifiers};
use termwiz::surface::change::Change;
use termwiz::surface::Position;
use termwiz::terminal::{ScreenSize, Terminal};

#[derive(Debug, Parser, Clone)]
pub struct ImgCatCommand {
    /// Specify the display width; defaults to "auto" which automatically selects
    /// an appropriate size.  You may also use an integer value `N` to specify the
    /// number of cells, or `Npx` to specify the number of pixels, or `N%` to
    /// size relative to the terminal width.
    #[arg(long = "width")]
    width: Option<ITermDimension>,

    /// Specify the display height; defaults to "auto" which automatically selects
    /// an appropriate size.
    #[arg(long = "height")]
    height: Option<ITermDimension>,

    /// Do not respect the aspect ratio.
    #[arg(long = "no-preserve-aspect-ratio")]
    no_preserve_aspect_ratio: bool,

    /// Set the cursor position prior to displaying the image.
    #[arg(long, value_parser=ValueParser::new(x_comma_y))]
    position: Option<ImagePosition>,

    /// Do not move the cursor after displaying the image.
    #[arg(long)]
    no_move_cursor: bool,

    /// Wait for enter/escape/ctrl-c/ctrl-d to be pressed after displaying
    #[arg(long)]
    hold: bool,

    /// How to manage passing the escape through to tmux
    #[arg(long, value_parser)]
    pub tmux_passthru: Option<TmuxPassthru>,

    /// Set the maximum number of pixels per image frame.
    #[arg(long, default_value = "25000000")]
    max_pixels: usize,

    /// Do not resample images whose frames are larger than max-pixels.
    #[arg(long)]
    no_resample: bool,

    /// Specify the image format to use for resampled images.
    #[arg(long, default_value = "input")]
    resample_format: ResampleImageFormat,

    /// Specify the filtering technique used when resizing/resampling.
    #[arg(long, default_value = "catmull-rom")]
    resample_filter: ResampleFilter,

    /// Pre-process the image to resize it to the specified dimensions.
    #[arg(long, name="WIDTHxHEIGHT", value_parser=ValueParser::new(width_x_height))]
    resize: Option<ImageDimension>,

    /// When resampling, display timing diagnostics.
    #[arg(long)]
    show_resample_timing: bool,

    /// The name of the image file to be displayed.
    #[arg(value_parser, value_hint=ValueHint::FilePath)]
    file_name: Option<OsString>,
}

#[derive(Clone, Copy, Debug)]
pub struct ImagePosition {
    x: u32,
    y: u32,
}

fn x_comma_y(arg: &str) -> Result<ImagePosition, String> {
    if let Some(eq) = arg.find(',') {
        let (left, right) = arg.split_at(eq);
        let x = left
            .parse()
            .map_err(|err| format!("Expected x,y integers, got {arg}. '{left}': {err:#}"))?;
        let y = right[1..]
            .parse()
            .map_err(|err| format!("Expected x,y integers, got {arg}. '{right}': {err:#}"))?;
        Ok(ImagePosition { x, y })
    } else {
        Err(format!("Expected x,y, but got {}", arg))
    }
}

#[derive(Clone, Copy, Debug)]
pub struct ImageDimension {
    width: u32,
    height: u32,
}

fn width_x_height(arg: &str) -> Result<ImageDimension, String> {
    if let Some(eq) = arg.find('x') {
        let (left, right) = arg.split_at(eq);
        let width = left
            .parse()
            .map_err(|err| format!("Expected WxH integers, got {arg}. '{left}': {err:#}"))?;
        let height = right[1..]
            .parse()
            .map_err(|err| format!("Expected WxH integers, got {arg}. '{right}': {err:#}"))?;
        Ok(ImageDimension { width, height })
    } else {
        Err(format!("Expected WxH, but got {}", arg))
    }
}

#[derive(Copy, Clone, Debug, ValueEnum, Default)]
pub enum ResampleFilter {
    Nearest,
    Triangle,
    #[default]
    CatmullRom,
    Gaussian,
    Lanczos3,
}

#[derive(Copy, Clone, Debug, ValueEnum, Default)]
pub enum ResampleImageFormat {
    Png,
    Jpeg,
    #[default]
    Input,
}

#[derive(Debug, Clone, Copy)]
pub struct ImageInfo {
    pub width: u32,
    pub height: u32,
    pub format: image::ImageFormat,
}

#[derive(Copy, Clone, Debug, ValueEnum, Default)]
pub enum TmuxPassthru {
    Disable,
    Enable,
    #[default]
    Detect,
}

impl TmuxPassthru {
    fn is_tmux() -> bool {
        std::env::var_os("TMUX").is_some()
    }

    pub fn enabled(&self) -> bool {
        match self {
            Self::Enable => true,
            Self::Detect => Self::is_tmux(),
            Self::Disable => false,
        }
    }

    pub fn encode(&self, content: String) -> String {
        if self.enabled() {
            let mut result = "\u{1b}Ptmux;".to_string();
            for c in content.chars() {
                if c == '\u{1b}' {
                    result.push(c);
                }
                result.push(c);
            }
            result.push_str("\u{1b}\\");
            result
        } else {
            content
        }
    }
}

impl ImgCatCommand {
    pub fn run(&self) -> anyhow::Result<()> {
        let (data, image_info) = self.get_image_data()?;

        let caps = Capabilities::new_from_env()?;
        let mut term = termwiz::terminal::new_terminal(caps)?;
        term.set_raw_mode()?;

        let mut probe = term
            .probe_capabilities()
            .ok_or_else(|| anyhow!("Terminal has no prober?"))?;

        let xt_version = probe.xt_version()?;
        let term_size = probe.screen_size()?;
        let is_tmux = xt_version.is_tmux();
        let is_conpty = cfg!(windows);

        let needs_force_cursor_move = !self.no_move_cursor
            && self.position.is_none()
            && (is_tmux || is_conpty)
            && (term_size.xpixel != 0 && term_size.ypixel != 0);

        term.set_cooked_mode()?;

        let save_cursor = Esc::Code(EscCode::DecSaveCursorPosition);
        let restore_cursor = Esc::Code(EscCode::DecRestoreCursorPosition);

        if let Some(position) = &self.position {
            let csi = termwiz::escape::CSI::Cursor(
                termwiz::escape::csi::Cursor::CharacterAndLinePosition {
                    col: OneBased::from_zero_based(position.x),
                    line: OneBased::from_zero_based(position.y),
                },
            );
            print!("{save_cursor}{csi}");
        }

        let image_dims = self.compute_image_cell_dimensions(image_info, term_size);

        if let ((_cursor_x, cursor_y), true) = (image_dims, needs_force_cursor_move) {
            let new_lines = "\n".repeat(cursor_y);
            print!("{new_lines}");
            term.render(&[Change::CursorPosition {
                x: Position::Absolute(0),
                y: Position::Relative(-1 * (cursor_y as isize)),
            }])?;
        }

        let osc = OperatingSystemCommand::ITermProprietary(ITermProprietary::File(Box::new(
            ITermFileData {
                name: None,
                size: Some(data.len()),
                width: self.width.unwrap_or_default(),
                height: self.height.unwrap_or_default(),
                preserve_aspect_ratio: !self.no_preserve_aspect_ratio,
                inline: true,
                do_not_move_cursor: self.no_move_cursor,
                data,
            },
        )));
        let encoded = self
            .tmux_passthru
            .unwrap_or_default()
            .encode(osc.to_string());
        println!("{encoded}");

        if let ((_cursor_x, cursor_y), true) = (image_dims, needs_force_cursor_move) {
            term.render(&[Change::CursorPosition {
                x: Position::Absolute(0),
                y: Position::Relative(cursor_y as isize),
            }])?;
        } else if self.position.is_some() {
            print!("{restore_cursor}");
        }

        if self.hold {
            term.set_raw_mode()?;
            while let Ok(Some(event)) = term.poll_input(None) {
                match event {
                    InputEvent::Key(
                        KeyEvent {
                            key: KeyCode::Enter | KeyCode::Escape,
                            modifiers: _,
                        }
                        | KeyEvent {
                            key: KeyCode::Char('c') | KeyCode::Char('d'),
                            modifiers: Modifiers::CTRL,
                        },
                    ) => break,
                    _ => {}
                }
            }
        }

        Ok(())
    }

    fn compute_image_cell_dimensions(
        &self,
        info: ImageInfo,
        term_size: ScreenSize,
    ) -> (usize, usize) {
        let physical_cols = term_size.cols;
        let physical_rows = term_size.rows;
        let cell_pixel_width = term_size.xpixel;
        let cell_pixel_height = term_size.ypixel;
        let pixel_width = cell_pixel_width * physical_cols;
        let pixel_height = cell_pixel_height * physical_rows;

        let width = self
            .width
            .unwrap_or_default()
            .to_pixels(cell_pixel_width, physical_cols);
        let height = self
            .height
            .unwrap_or_default()
            .to_pixels(cell_pixel_height, physical_rows);

        let aspect = info.width as f32 / info.height as f32;

        let (width, height) = match (width, height) {
            (None, None) => {
                let width = info.width as usize;
                let height = info.height as usize;
                if width > pixel_width || height > pixel_height {
                    let width = width as f32;
                    let height = height as f32;
                    let mut candidates = vec![];

                    let x_scale = pixel_width as f32 / width;
                    if height * x_scale <= pixel_height as f32 {
                        candidates.push((pixel_width, (height * x_scale) as usize));
                    }
                    let y_scale = pixel_height as f32 / height;
                    if width * y_scale <= pixel_width as f32 {
                        candidates.push(((width * y_scale) as usize, pixel_height));
                    }

                    candidates.sort_by(|a, b| (a.0 * a.1).cmp(&(b.0 * b.1)));
                    candidates.pop().unwrap()
                } else {
                    (width, height)
                }
            }
            (Some(w), None) => {
                let h = w as f32 / aspect;
                (w, h as usize)
            }
            (None, Some(h)) => {
                let w = h as f32 * aspect;
                (w as usize, h)
            }
            (Some(w), Some(_)) if !self.no_preserve_aspect_ratio => {
                let h = w as f32 / aspect;
                (w, h as usize)
            }
            (Some(w), Some(h)) => (w, h),
        };

        (width / cell_pixel_width, height / cell_pixel_height)
    }

    fn image_dimensions(data: &[u8]) -> anyhow::Result<ImageInfo> {
        let reader = image::ImageReader::new(std::io::Cursor::new(data)).with_guessed_format()?;
        let format = reader
            .format()
            .ok_or_else(|| anyhow::anyhow!("unknown image format!?"))?;
        let (width, height) = reader.into_dimensions()?;
        Ok(ImageInfo {
            width,
            height,
            format,
        })
    }

    fn resize_image(
        &self,
        data: &[u8],
        target_width: u32,
        target_height: u32,
        image_info: ImageInfo,
    ) -> anyhow::Result<(Vec<u8>, ImageInfo)> {
        let start = std::time::Instant::now();
        let im = image::load_from_memory(data).with_context(|| match self.file_name.as_ref() {
            Some(file_name) => format!("loading image from file {file_name:?}"),
            None => "loading image from stdin".to_string(),
        })?;
        if self.show_resample_timing {
            eprintln!(
                "loading image took {:?} for {} bytes -> {image_info:?}",
                start.elapsed(),
                data.len()
            );
        }

        let start = std::time::Instant::now();
        use image::imageops::FilterType;
        let filter = match self.resample_filter {
            ResampleFilter::Nearest => FilterType::Nearest,
            ResampleFilter::Triangle => FilterType::Triangle,
            ResampleFilter::CatmullRom => FilterType::CatmullRom,
            ResampleFilter::Gaussian => FilterType::Gaussian,
            ResampleFilter::Lanczos3 => FilterType::Lanczos3,
        };
        let im = im.resize_to_fill(target_width, target_height, filter);
        if self.show_resample_timing {
            eprintln!("resizing took {:?}", start.elapsed());
        }

        let mut data = vec![];
        let start = std::time::Instant::now();

        let output_format = match self.resample_format {
            ResampleImageFormat::Png => image::ImageFormat::Png,
            ResampleImageFormat::Jpeg => image::ImageFormat::Jpeg,
            ResampleImageFormat::Input => image_info.format,
        };
        im.write_to(&mut std::io::Cursor::new(&mut data), output_format)
            .with_context(|| format!("encoding resampled image as {output_format:?}"))?;

        let new_info = ImageInfo {
            width: target_width,
            height: target_height,
            format: output_format,
        };

        if self.show_resample_timing {
            eprintln!(
                "encoding took {:?} to produce {} bytes -> {new_info:?}",
                start.elapsed(),
                data.len()
            );
        }

        Ok((data, new_info))
    }

    fn get_image_data(&self) -> anyhow::Result<(Vec<u8>, ImageInfo)> {
        let mut data = Vec::new();
        if let Some(file_name) = self.file_name.as_ref() {
            let mut f = std::fs::File::open(file_name)
                .with_context(|| anyhow!("reading image file: {:?}", file_name))?;
            f.read_to_end(&mut data)?;
        } else {
            let mut stdin = std::io::stdin();
            stdin.read_to_end(&mut data)?;
        }

        let image_info = Self::image_dimensions(&data)?;

        let (data, image_info) = if let Some(dimension) = self.resize {
            self.resize_image(&data, dimension.width, dimension.height, image_info)?
        } else {
            (data, image_info)
        };

        let total_pixels = image_info.width.saturating_mul(image_info.height) as usize;

        if !self.no_resample && total_pixels > self.max_pixels {
            let max_area = self.max_pixels as f32;
            let area = total_pixels as f32;
            let scale = area / max_area;
            let target_width = (image_info.width as f32 / scale).floor() as u32;
            let target_height = (image_info.height as f32 / scale).floor() as u32;
            self.resize_image(&data, target_width, target_height, image_info)
        } else {
            Ok((data, image_info))
        }
    }
}
