//! CX Terminal: Workspace snapshot commands
//!
//! Save and restore workspace snapshots.
//! Example: cx save my-project
//! Example: cx restore my-project
//! Example: cx snapshots list

use anyhow::{Context, Result};
use clap::Parser;
use std::fs;
use std::path::PathBuf;
use std::process::Command;

/// Save current workspace as a snapshot
#[derive(Debug, Parser, Clone)]
pub struct SaveCommand {
    /// Snapshot name
    #[arg(value_parser)]
    pub name: String,

    /// Directory to snapshot (defaults to current directory)
    #[arg(long, short = 'd')]
    pub directory: Option<PathBuf>,

    /// Overwrite existing snapshot
    #[arg(long, short = 'f')]
    pub force: bool,

    /// Verbose output
    #[arg(long, short = 'v')]
    pub verbose: bool,

    /// Include node_modules, .venv, target directories
    #[arg(long)]
    pub include_deps: bool,
}

/// Restore a workspace from a snapshot
#[derive(Debug, Parser, Clone)]
pub struct RestoreCommand {
    /// Snapshot name to restore
    #[arg(value_parser)]
    pub name: String,

    /// Directory to restore to (defaults to current directory)
    #[arg(long, short = 'd')]
    pub directory: Option<PathBuf>,

    /// Overwrite existing files
    #[arg(long, short = 'f')]
    pub force: bool,

    /// Verbose output
    #[arg(long, short = 'v')]
    pub verbose: bool,
}

/// List available snapshots
#[derive(Debug, Parser, Clone)]
pub struct SnapshotsCommand {
    /// Show detailed information
    #[arg(long, short = 'l')]
    pub long: bool,

    /// Delete a snapshot
    #[arg(long)]
    pub delete: Option<String>,
}

fn get_snapshots_dir() -> Result<PathBuf> {
    let home = std::env::var("HOME").context("HOME environment variable not set")?;
    let snapshots_dir = PathBuf::from(home).join(".cx").join("snapshots");

    if !snapshots_dir.exists() {
        fs::create_dir_all(&snapshots_dir)
            .with_context(|| format!("Failed to create snapshots directory: {:?}", snapshots_dir))?;
    }

    Ok(snapshots_dir)
}

impl SaveCommand {
    pub fn run(&self) -> Result<()> {
        let snapshots_dir = get_snapshots_dir()?;
        let source_dir = self
            .directory
            .clone()
            .unwrap_or_else(|| PathBuf::from("."));

        // Resolve to absolute path
        let source_dir = source_dir
            .canonicalize()
            .with_context(|| format!("Failed to resolve path: {:?}", source_dir))?;

        // Safety check: warn if trying to save home directory or large directories
        let home = std::env::var("HOME").ok();
        if let Some(home_path) = &home {
            if source_dir.to_str() == Some(home_path) {
                anyhow::bail!(
                    "Cannot snapshot entire home directory. Use -d to specify a project directory.\n\
                     Example: cx save my-project -d ./my-project"
                );
            }
        }

        // Check directory size (rough estimate based on file count)
        let file_count = fs::read_dir(&source_dir)
            .map(|entries| entries.count())
            .unwrap_or(0);

        if file_count > 1000 && !self.force {
            anyhow::bail!(
                "Directory has {} items. This might be too large.\n\
                 Use --force to proceed anyway, or use -d to specify a smaller directory.",
                file_count
            );
        }

        let snapshot_path = snapshots_dir.join(format!("{}.tar.gz", self.name));

        if snapshot_path.exists() && !self.force {
            anyhow::bail!(
                "Snapshot '{}' already exists. Use --force to overwrite.",
                self.name
            );
        }

        println!(
            "Saving workspace '{}' to snapshot '{}'...",
            source_dir.display(),
            self.name
        );

        // Build exclude patterns - always exclude common large/cache directories
        let mut exclude_args = vec![
            "--exclude=node_modules",
            "--exclude=.venv",
            "--exclude=venv",
            "--exclude=target",
            "--exclude=.git",
            "--exclude=__pycache__",
            "--exclude=.next",
            "--exclude=dist",
            "--exclude=build",
            "--exclude=*.pyc",
            // Additional safety exclusions
            "--exclude=.cache",
            "--exclude=.npm",
            "--exclude=.cargo",
            "--exclude=Library",
            "--exclude=.Trash",
            "--exclude=*.log",
        ];

        if self.include_deps {
            // Only keep minimal exclusions
            exclude_args = vec![
                "--exclude=.git",
                "--exclude=.Trash",
            ];
        }

        // Create tarball
        let mut args = vec!["-czf", snapshot_path.to_str().unwrap()];
        args.extend(exclude_args.iter().map(|s| *s));
        args.extend_from_slice(&["-C", source_dir.parent().unwrap().to_str().unwrap()]);
        args.push(source_dir.file_name().unwrap().to_str().unwrap());

        if self.verbose {
            println!("Running: tar {}", args.join(" "));
        }

        let output = Command::new("tar")
            .args(&args)
            .output()
            .context("Failed to run tar command")?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            anyhow::bail!("tar command failed: {}", stderr);
        }

        // Get file size
        let metadata = fs::metadata(&snapshot_path)?;
        let size_mb = metadata.len() as f64 / 1024.0 / 1024.0;

        println!(
            "✅ Snapshot '{}' saved ({:.2} MB)",
            self.name, size_mb
        );
        println!("   Location: {}", snapshot_path.display());
        println!("   Restore with: cx restore {}", self.name);

        Ok(())
    }
}

impl RestoreCommand {
    pub fn run(&self) -> Result<()> {
        let snapshots_dir = get_snapshots_dir()?;
        let snapshot_path = snapshots_dir.join(format!("{}.tar.gz", self.name));

        if !snapshot_path.exists() {
            anyhow::bail!(
                "Snapshot '{}' not found. Use 'cx snapshots' to list available snapshots.",
                self.name
            );
        }

        let target_dir = self
            .directory
            .clone()
            .unwrap_or_else(|| PathBuf::from("."));

        // Check if target directory exists and has files
        if target_dir.exists() && target_dir.read_dir()?.next().is_some() {
            if !self.force {
                anyhow::bail!(
                    "Directory '{}' is not empty. Use --force to overwrite.",
                    target_dir.display()
                );
            }
        }

        // Create target directory if needed
        fs::create_dir_all(&target_dir)
            .with_context(|| format!("Failed to create directory: {:?}", target_dir))?;

        println!(
            "Restoring snapshot '{}' to '{}'...",
            self.name,
            target_dir.display()
        );

        // Extract tarball
        let args = [
            "-xzf",
            snapshot_path.to_str().unwrap(),
            "-C",
            target_dir.to_str().unwrap(),
            "--strip-components=1",
        ];

        if self.verbose {
            println!("Running: tar {}", args.join(" "));
        }

        let output = Command::new("tar")
            .args(&args)
            .output()
            .context("Failed to run tar command")?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            anyhow::bail!("tar command failed: {}", stderr);
        }

        println!("✅ Snapshot '{}' restored to '{}'", self.name, target_dir.display());

        Ok(())
    }
}

impl SnapshotsCommand {
    pub fn run(&self) -> Result<()> {
        let snapshots_dir = get_snapshots_dir()?;

        // Handle delete
        if let Some(name) = &self.delete {
            let snapshot_path = snapshots_dir.join(format!("{}.tar.gz", name));
            if snapshot_path.exists() {
                fs::remove_file(&snapshot_path)?;
                println!("✅ Deleted snapshot '{}'", name);
            } else {
                anyhow::bail!("Snapshot '{}' not found", name);
            }
            return Ok(());
        }

        // List snapshots
        let mut snapshots: Vec<_> = fs::read_dir(&snapshots_dir)?
            .filter_map(|e| e.ok())
            .filter(|e| {
                e.path()
                    .extension()
                    .map(|ext| ext == "gz")
                    .unwrap_or(false)
            })
            .collect();

        if snapshots.is_empty() {
            println!("No snapshots found.");
            println!("Create one with: cx save <name>");
            return Ok(());
        }

        // Sort by modification time (newest first)
        snapshots.sort_by(|a, b| {
            let a_time = a.metadata().and_then(|m| m.modified()).ok();
            let b_time = b.metadata().and_then(|m| m.modified()).ok();
            b_time.cmp(&a_time)
        });

        println!("Available snapshots:\n");

        if self.long {
            println!("{:<20} {:>10} {}", "NAME", "SIZE", "MODIFIED");
            println!("{}", "-".repeat(50));
        }

        for entry in snapshots {
            let path = entry.path();
            let name = path
                .file_stem()
                .and_then(|s| s.to_str())
                .unwrap_or("unknown")
                .trim_end_matches(".tar");

            if self.long {
                let metadata = entry.metadata()?;
                let size = metadata.len();
                let size_str = if size >= 1024 * 1024 {
                    format!("{:.1} MB", size as f64 / 1024.0 / 1024.0)
                } else if size >= 1024 {
                    format!("{:.1} KB", size as f64 / 1024.0)
                } else {
                    format!("{} B", size)
                };

                let modified = metadata.modified().ok();
                let time_str = if let Some(time) = modified {
                    let duration = std::time::SystemTime::now()
                        .duration_since(time)
                        .unwrap_or_default();
                    if duration.as_secs() < 60 {
                        "just now".to_string()
                    } else if duration.as_secs() < 3600 {
                        format!("{} min ago", duration.as_secs() / 60)
                    } else if duration.as_secs() < 86400 {
                        format!("{} hours ago", duration.as_secs() / 3600)
                    } else {
                        format!("{} days ago", duration.as_secs() / 86400)
                    }
                } else {
                    "unknown".to_string()
                };

                println!("{:<20} {:>10} {}", name, size_str, time_str);
            } else {
                println!("  {}", name);
            }
        }

        if !self.long {
            println!("\nUse 'cx snapshots -l' for detailed information.");
        }

        Ok(())
    }
}
