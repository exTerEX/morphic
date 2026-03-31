package shared

import (
	"os"
	"os/exec"
	"runtime"
	"strings"
)

// OpenNativeFolderDialog opens a native folder selection dialog.
// Returns the selected folder path or empty string if cancelled.
func OpenNativeFolderDialog() (string, error) {
	// Test mode: allow test to set folder via environment
	if testFolder := os.Getenv("MORPHIC_TEST_FOLDER"); testFolder != "" {
		return testFolder, nil
	}

	switch runtime.GOOS {
	case "linux":
		return linuxFolderDialog()
	case "darwin":
		return macFolderDialog()
	case "windows":
		return windowsFolderDialog()
	default:
		return "", nil
	}
}

func linuxFolderDialog() (string, error) {
	// Try zenity first
	if path, err := exec.LookPath("zenity"); err == nil && path != "" {
		cmd := exec.Command("zenity", "--file-selection", "--directory", "--title=Select Folder")
		out, err := cmd.Output()
		if err == nil {
			return strings.TrimSpace(string(out)), nil
		}
	}

	// Try kdialog
	if path, err := exec.LookPath("kdialog"); err == nil && path != "" {
		cmd := exec.Command("kdialog", "--getexistingdirectory", ".")
		out, err := cmd.Output()
		if err == nil {
			return strings.TrimSpace(string(out)), nil
		}
	}

	return "", nil
}

func macFolderDialog() (string, error) {
	cmd := exec.Command("osascript", "-e", `POSIX path of (choose folder with prompt "Select Folder")`)
	out, err := cmd.Output()
	if err != nil {
		return "", nil
	}
	return strings.TrimSpace(string(out)), nil
}

func windowsFolderDialog() (string, error) {
	script := `Add-Type -AssemblyName System.Windows.Forms; $f = New-Object System.Windows.Forms.FolderBrowserDialog; if ($f.ShowDialog() -eq 'OK') { $f.SelectedPath }`
	cmd := exec.Command("powershell", "-NoProfile", "-Command", script)
	out, err := cmd.Output()
	if err != nil {
		return "", nil
	}
	return strings.TrimSpace(string(out)), nil
}
