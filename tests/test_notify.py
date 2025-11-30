import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
import json
from pathlib import Path
from datetime import datetime, time

# Add parent directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cortex.notify import NotificationManager, NotifyConfig, notify_cli

class TestNotificationManager(unittest.TestCase):
    
    def setUp(self):
        self.mgr = NotificationManager()

    @patch("cortex.notify.CONFIG_FILE")
    @patch("builtins.open", new_callable=mock_open, read_data='{"enabled": true}')
    def test_load_config_exists(self, mock_file, mock_path):
        mock_path.exists.return_value = True
        cfg = self.mgr._load_config()
        self.assertTrue(cfg.enabled)

    @patch("cortex.notify.CONFIG_FILE")
    def test_load_config_missing(self, mock_path):
        mock_path.exists.return_value = False
        cfg = self.mgr._load_config()
        self.assertTrue(cfg.enabled)

    @patch("cortex.notify.CONFIG_FILE")
    def test_load_config_corrupt(self, mock_path):
        # Case: Config file is corrupted JSON
        mock_path.exists.return_value = True
        with patch("builtins.open", new_callable=mock_open, read_data='{invalid_json}'):
            cfg = self.mgr._load_config()
            self.assertTrue(cfg.enabled) # Should fallback to default

    @patch("cortex.notify.CONFIG_FILE")
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.mkdir")
    def test_save_config(self, mock_mkdir, mock_file, mock_path):
        self.mgr.save_config()
        mock_file.assert_called()

    @patch("cortex.notify.datetime")
    def test_dnd_active(self, mock_dt):
        mock_dt.now.return_value.time.return_value = time(23, 0)
        mock_dt.strptime = datetime.strptime
        
        self.mgr.config.dnd_start = "22:00"
        self.mgr.config.dnd_end = "08:00"
        self.assertTrue(self.mgr._is_dnd_active())

        mock_dt.now.return_value.time.return_value = time(9, 0)
        self.assertFalse(self.mgr._is_dnd_active())

    def test_dnd_invalid_config(self):
        # Case: Invalid time format in config
        self.mgr.config.dnd_start = "invalid"
        self.assertFalse(self.mgr._is_dnd_active())

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_send_success(self, mock_run, mock_which):
        mock_which.return_value = "/usr/bin/notify-send"
        with patch.object(self.mgr, '_is_dnd_active', return_value=False):
            res = self.mgr.send("Test", "Msg")
            self.assertTrue(res)

    @patch("shutil.which")
    @patch("builtins.print")
    def test_send_missing_binary(self, mock_print, mock_which):
        # Case: notify-send not found (Console fallback)
        mock_which.return_value = None
        with patch.object(self.mgr, '_is_dnd_active', return_value=False):
            res = self.mgr.send("Test", "Msg")
            self.assertTrue(res)
            mock_print.assert_called()

    def test_send_suppressed(self):
        # Case: DND is active
        with patch.object(self.mgr, '_is_dnd_active', return_value=True):
            res = self.mgr.send("Test", "Msg", level="normal")
            self.assertFalse(res)
            
            # Critical should bypass DND (Mocking subprocess to avoid error)
            with patch("shutil.which"), patch("subprocess.run"):
                res_crit = self.mgr.send("Test", "Msg", level="critical")
                self.assertTrue(res_crit)

    @patch("cortex.notify.NotificationManager.send")
    @patch("builtins.print")
    def test_cli_send(self, mock_print, mock_send):
        # Success case
        mock_send.return_value = True
        notify_cli("Title", "Msg")
        mock_print.assert_called_with("✅ Notification sent.")
        
        # Suppressed case
        mock_send.return_value = False
        notify_cli("Title", "Msg")
        # verify print called with suppressed message

    @patch("cortex.notify.NotificationManager.save_config")
    @patch("builtins.print")
    def test_cli_toggle(self, mock_print, mock_save):
        notify_cli("", "", dnd_toggle=True)
        mock_save.assert_called()

    @patch("builtins.print")
    def test_cli_configure(self, mock_print):
        notify_cli("", "", configure=True)
        mock_print.assert_called()

if __name__ == '__main__':
    unittest.main()
