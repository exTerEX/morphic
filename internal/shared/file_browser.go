package shared

import (
	"os"
	"os/exec"
	"runtime"
	"strings"
)

// OpenNativeFolderDialog opens a native folder selection dialog.
// Returns the selected folder path, whether a dialog tool is available, and any error.
func OpenNativeFolderDialog() (string, bool, error) {
	// Test mode: allow test to set folder via environment
	if testFolder := os.Getenv("MORPHIC_TEST_FOLDER"); testFolder != "" {
		return testFolder, true, nil
	}

	switch runtime.GOOS {
	case "linux":
		return linuxFolderDialog()
	case "darwin":
		return macFolderDialog()
	case "windows":
		return windowsFolderDialog()
	default:
		return "", false, nil
	}
}

func linuxFolderDialog() (string, bool, error) {
	// Try zenity first
	if path, err := exec.LookPath("zenity"); err == nil && path != "" {
		cmd := exec.Command("zenity", "--file-selection", "--directory", "--title=Select Folder")
		out, err := cmd.Output()
		if err == nil {
			return strings.TrimSpace(string(out)), true, nil
		}
		return "", true, nil // tool available but user cancelled
	}

	// Try kdialog
	if path, err := exec.LookPath("kdialog"); err == nil && path != "" {
		cmd := exec.Command("kdialog", "--getexistingdirectory", ".")
		out, err := cmd.Output()
		if err == nil {
			return strings.TrimSpace(string(out)), true, nil
		}
		return "", true, nil // tool available but user cancelled
	}

	// No dialog tool found
	return "", false, nil
}

func macFolderDialog() (string, bool, error) {
	cmd := exec.Command("osascript", "-e", `POSIX path of (choose folder with prompt "Select Folder")`)
	out, err := cmd.Output()
	if err != nil {
		return "", true, nil
	}
	return strings.TrimSpace(string(out)), true, nil
}

func windowsFolderDialog() (string, bool, error) {
	script := `Add-Type -AssemblyName System.Windows.Forms; $f = New-Object System.Windows.Forms.FolderBrowserDialog; if ($f.ShowDialog() -eq 'OK') { $f.SelectedPath }`
	cmd := exec.Command("powershell", "-NoProfile", "-Command", script)
	out, err := cmd.Output()
	if err != nil {
		return "", true, nil
	}
	return strings.TrimSpace(string(out)), true, nil
}
