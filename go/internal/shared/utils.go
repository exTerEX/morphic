package shared

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// FileInfo holds metadata about a discovered file.
type FileInfo struct {
	Path string
	Name string
	Size int64
	Ext  string
}

// FindFilesByExtension walks the folder tree once and returns all files
// matching the given extensions. This replaces the Python version which
// called rglob() twice per extension (82+ traversals).
func FindFilesByExtension(folder string, extensions map[string]struct{}, excludedFolders map[string]struct{}) ([]FileInfo, error) {
	var files []FileInfo
	seen := make(map[string]struct{})

	err := filepath.WalkDir(folder, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return nil // skip inaccessible entries
		}

		if d.IsDir() {
			name := strings.ToLower(d.Name())
			if _, excluded := excludedFolders[name]; excluded {
				return filepath.SkipDir
			}
			return nil
		}

		ext := strings.ToLower(filepath.Ext(path))
		if alias, ok := Aliases[ext]; ok {
			ext = alias
		}

		if _, ok := extensions[ext]; !ok {
			return nil
		}

		// Deduplicate by resolved path
		abs, err := filepath.Abs(path)
		if err != nil {
			abs = path
		}
		if _, dup := seen[abs]; dup {
			return nil
		}
		seen[abs] = struct{}{}

		info, err := d.Info()
		if err != nil {
			return nil
		}

		files = append(files, FileInfo{
			Path: abs,
			Name: d.Name(),
			Size: info.Size(),
			Ext:  ext,
		})

		return nil
	})

	if err != nil {
		return nil, err
	}

	sort.Slice(files, func(i, j int) bool {
		return files[i].Path < files[j].Path
	})

	return files, nil
}

// IsExcludedPath checks if any component of the path is in the exclusion set.
func IsExcludedPath(path string, excludedFolders map[string]struct{}) bool {
	parts := strings.Split(filepath.ToSlash(path), "/")
	for _, part := range parts {
		if _, excluded := excludedFolders[strings.ToLower(part)]; excluded {
			return true
		}
	}
	return false
}

// FindImageFiles returns all image files in the given folder.
func FindImageFiles(folder string) ([]FileInfo, error) {
	return FindFilesByExtension(folder, ImageExtensions, ExcludedFolders)
}

// FindVideoFiles returns all video files in the given folder.
func FindVideoFiles(folder string) ([]FileInfo, error) {
	return FindFilesByExtension(folder, VideoExtensions, ExcludedFolders)
}

// FindAllMediaFiles returns all image and video files.
func FindAllMediaFiles(folder string) ([]FileInfo, error) {
	allExts := make(map[string]struct{})
	for k, v := range ImageExtensions {
		allExts[k] = v
	}
	for k, v := range VideoExtensions {
		allExts[k] = v
	}
	return FindFilesByExtension(folder, allExts, ExcludedFolders)
}

// FormatFileSize formats file size in human-readable format.
func FormatFileSize(sizeBytes int64) string {
	size := float64(sizeBytes)
	for _, unit := range []string{"B", "KB", "MB", "GB"} {
		if size < 1024 {
			return fmt.Sprintf("%.2f %s", size, unit)
		}
		size /= 1024
	}
	return fmt.Sprintf("%.2f TB", size)
}

// FormatDuration formats duration in human-readable format.
func FormatDuration(seconds float64) string {
	hours := int(seconds) / 3600
	minutes := (int(seconds) % 3600) / 60
	secs := int(seconds) % 60
	if hours > 0 {
		return fmt.Sprintf("%dh %dm %ds", hours, minutes, secs)
	}
	if minutes > 0 {
		return fmt.Sprintf("%dm %ds", minutes, secs)
	}
	return fmt.Sprintf("%ds", secs)
}
