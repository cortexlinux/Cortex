import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
import json
from pathlib import Path

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
        self.assertTrue(cfg.enabled) # Default

    @patch("cortex.notify.CONFIG_FILE")
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.mkdir")
    def test_save_config(self, mock_mkdir, mock_file, mock_path):
        self.mgr.save_config()
        mock_file.assert_called()

    @patch("cortex.notify.datetime")
    def test_dnd_active(self, mock_dt):
        # Case: 22:00 - 08:00. Current: 23:00 (Active)
        mock_dt.now.return_value.time.return_value = time(23, 0)
        from datetime import time
        
        self.mgr.config.dnd_start = "22:00"
        self.mgr.config.dnd_end = "08:00"
        self.assertTrue(self.mgr._is_dnd_active())

        # Case: Current 09:00 (Inactive)
        mock_dt.now.return_value.time.return_value = time(9, 0)
        self.assertFalse(self.mgr._is_dnd_active())

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_send_success(self, mock_run, mock_which):
        mock_which.return_value = "/usr/bin/notify-send"
        
        # Force DND off for test
        with patch.object(self.mgr, '_is_dnd_active', return_value=False):
            res = self.mgr.send("Test", "Msg")
            self.assertTrue(res)
            mock_run.assert_called()

    def test_send_suppressed(self):
        with patch.object(self.mgr, '_is_dnd_active', return_value=True):
            res = self.mgr.send("Test", "Msg")
            self.assertFalse(res)

    @patch("cortex.notify.NotificationManager.send")
    @patch("builtins.print")
    def test_cli_send(self, mock_print, mock_send):
        mock_send.return_value = True
        notify_cli("Title", "Msg")
        mock_print.assert_called_with("✅ Notification sent.")

    @patch("cortex.notify.NotificationManager.save_config")
    @patch("builtins.print")
    def test_cli_toggle(self, mock_print, mock_save):
        notify_cli("", "", dnd_toggle=True)
        mock_save.assert_called()

if __name__ == '__main__':
    unittest.main()
