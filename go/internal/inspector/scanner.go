package inspector

import (
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/exterex/morphic/internal/shared"
)

// ScanJob represents a running or completed inspector job.
type ScanJob struct {
	shared.Job
	mu sync.Mutex

	Folder    string                   `json:"folder"`
	Mode      string                   `json:"mode"` // "exif" or "integrity"
	Results   []map[string]interface{} `json:"results,omitempty"`
	Total     int                      `json:"total"`
	Processed int                      `json:"processed"`
}

var store = shared.NewJobStore[ScanJob]()

func init() {
	store.StartCleanup(30*time.Minute, func(j *ScanJob) time.Time {
		return j.DoneAt
	})
}

// StartJob creates and launches a new inspector job.
func StartJob(folder, mode string) string {
	job := &ScanJob{
		Job:    shared.NewJob(),
		Folder: folder,
		Mode:   mode,
	}
	job.Status = shared.JobStatusRunning
	store.Set(job.ID, job)
	go runScan(job)
	return job.ID
}

// GetJob retrieves a job by ID.
func GetJob(id string) (*ScanJob, bool) {
	return store.Get(id)
}

func runScan(job *ScanJob) {
	defer func() {
		if r := recover(); r != nil {
			job.mu.Lock()
			job.Status = shared.JobStatusFailed
			job.Error = fmt.Sprintf("%v", r)
			job.DoneAt = time.Now()
			job.mu.Unlock()
		}
	}()

	job.mu.Lock()
	job.Message = fmt.Sprintf("Scanning folder: %s", job.Folder)
	job.mu.Unlock()

	// Determine extensions to look for
	var exts map[string]struct{}
	if job.Mode == "exif" {
		exts = shared.ImageExtensions
	} else {
		exts = make(map[string]struct{})
		for k, v := range shared.ImageExtensions {
			exts[k] = v
		}
		for k, v := range shared.VideoExtensions {
			exts[k] = v
		}
	}

	files, err := shared.FindFilesByExtension(job.Folder, exts, shared.ExcludedFolders)
	if err != nil {
		job.mu.Lock()
		job.Status = shared.JobStatusFailed
		job.Error = err.Error()
		job.DoneAt = time.Now()
		job.mu.Unlock()
		return
	}

	job.mu.Lock()
	job.Total = len(files)
	job.mu.Unlock()

	if len(files) == 0 {
		job.mu.Lock()
		job.Status = shared.JobStatusDone
		job.Progress = 1.0
		job.DoneAt = time.Now()
		job.Message = "No files found."
		job.mu.Unlock()
		return
	}

	if job.Mode == "exif" {
		scanExif(job, files)
	} else {
		scanIntegrity(job, files)
	}

	job.mu.Lock()
	job.Status = shared.JobStatusDone
	job.Progress = 1.0
	job.DoneAt = time.Now()
	elapsed := job.DoneAt.Sub(job.StartedAt).Seconds()
	job.Message = fmt.Sprintf("Done! Processed %d files in %s.",
		job.Processed, shared.FormatDuration(elapsed))
	job.mu.Unlock()
}

func scanExif(job *ScanJob, files []shared.FileInfo) {
	for i, f := range files {
		if !shared.IsImage(f.Path) {
			continue
		}

		item := map[string]interface{}{
			"path":      f.Path,
			"filename":  filepath.Base(f.Path),
			"directory": filepath.Dir(f.Path),
			"has_exif":  false,
			"has_gps":   false,
		}

		exifData, err := ReadExif(f.Path)
		if err != nil {
			item["exif"] = ExifData{}
			item["error"] = err.Error()
		} else {
			item["exif"] = exifData
			item["has_exif"] = len(exifData) > 0
			_, hasGPS := exifData["_gps_lat"]
			item["has_gps"] = hasGPS
		}

		job.mu.Lock()
		job.Results = append(job.Results, item)
		job.Processed = i + 1
		job.Progress = float64(i+1) / float64(job.Total)
		job.Message = fmt.Sprintf("Reading EXIF: %d/%d", i+1, job.Total)
		job.mu.Unlock()
	}
}

func scanIntegrity(job *ScanJob, files []shared.FileInfo) {
	for i, f := range files {
		var result IntegrityResult
		if shared.IsImage(f.Path) {
			result = CheckImage(f.Path)
		} else if shared.IsVideo(f.Path) {
			result = CheckVideo(f.Path)
		} else {
			result = IntegrityResult{
				Path:  f.Path,
				Type:  "unknown",
				Error: "Unknown file type",
			}
		}
		result.Filename = filepath.Base(f.Path)
		result.Directory = filepath.Dir(f.Path)

		item := map[string]interface{}{
			"path":           result.Path,
			"valid":          result.Valid,
			"error":          nilIfEmpty(result.Error),
			"size":           result.Size,
			"size_formatted": result.SizeFormatted,
			"width":          result.Width,
			"height":         result.Height,
			"type":           result.Type,
			"filename":       result.Filename,
			"directory":      result.Directory,
		}
		if result.Format != "" {
			item["format"] = result.Format
		}
		if result.Codec != "" {
			item["codec"] = result.Codec
		}
		if result.Duration > 0 {
			item["duration"] = result.Duration
		}

		job.mu.Lock()
		job.Results = append(job.Results, item)
		job.Processed = i + 1
		job.Progress = float64(i+1) / float64(job.Total)
		job.Message = fmt.Sprintf("Checking: %d/%d", i+1, job.Total)
		job.mu.Unlock()
	}
}

func nilIfEmpty(s string) interface{} {
	if s == "" {
		return nil
	}
	return s
}

// Stat checks if a path exists.
func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}
