package resizer

import (
	"fmt"
	"os"
	"sync"
	"time"

	"github.com/exterex/morphic/internal/shared"
)

// ScanJob represents a running or completed resize job.
type ScanJob struct {
	shared.Job
	mu sync.Mutex

	Folder       string                   `json:"folder"`
	Width        int                      `json:"width"`
	Height       int                      `json:"height"`
	Mode         string                   `json:"mode"`
	OutputFolder string                   `json:"output_folder,omitempty"`
	BgColor      string                   `json:"bg_color"`
	Quality      int                      `json:"quality"`
	Total        int                      `json:"total"`
	Processed    int                      `json:"processed"`
	Results      []map[string]interface{} `json:"results,omitempty"`
	Errors       []map[string]interface{} `json:"errors,omitempty"`
}

var store = shared.NewJobStore[ScanJob]()

func init() {
	store.StartCleanup(30*time.Minute, func(j *ScanJob) time.Time {
		return j.DoneAt
	})
}

// StartJob creates and launches a new resize job.
func StartJob(folder string, width, height int, mode, outputFolder, bgColor string, quality int) string {
	job := &ScanJob{
		Job:          shared.NewJob(),
		Folder:       folder,
		Width:        width,
		Height:       height,
		Mode:         mode,
		OutputFolder: outputFolder,
		BgColor:      bgColor,
		Quality:      quality,
	}
	job.Status = shared.JobStatusRunning
	store.Set(job.ID, job)
	go runResize(job)
	return job.ID
}

// GetJob retrieves a job by ID.
func GetJob(id string) (*ScanJob, bool) {
	return store.Get(id)
}

func runResize(job *ScanJob) {
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

	files, err := shared.FindImageFiles(job.Folder)
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
		job.Message = "No image files found."
		job.mu.Unlock()
		return
	}

	errCount := 0
	for i, f := range files {
		origSize := f.Size
		dest, resizeErr := ResizeImage(
			f.Path, job.Width, job.Height, job.Mode,
			job.OutputFolder, job.BgColor, job.Quality, "",
		)

		result := map[string]interface{}{
			"source": f.Path,
		}

		if resizeErr != nil {
			errCount++
			result["destination"] = nil
			result["status"] = "error"
			result["error"] = resizeErr.Error()

			job.mu.Lock()
			job.Errors = append(job.Errors, map[string]interface{}{
				"path":  f.Path,
				"error": resizeErr.Error(),
			})
			job.mu.Unlock()
		} else {
			var newSize int64
			if info, err := os.Stat(dest); err == nil {
				newSize = info.Size()
			}
			result["destination"] = dest
			result["status"] = "ok"
			result["original_size"] = origSize
			result["new_size"] = newSize
			result["original_size_fmt"] = shared.FormatFileSize(origSize)
			result["new_size_fmt"] = shared.FormatFileSize(newSize)
		}

		job.mu.Lock()
		job.Results = append(job.Results, result)
		job.Processed = i + 1
		job.Progress = float64(i+1) / float64(job.Total)
		job.Message = fmt.Sprintf("Resizing: %d/%d (%d errors)", i+1, job.Total, errCount)
		job.mu.Unlock()
	}

	job.mu.Lock()
	job.Status = shared.JobStatusDone
	job.Progress = 1.0
	job.DoneAt = time.Now()
	elapsed := job.DoneAt.Sub(job.StartedAt).Seconds()
	job.Message = fmt.Sprintf("Done! Resized %d images in %s. %d error(s).",
		job.Processed, shared.FormatDuration(elapsed), errCount)
	job.mu.Unlock()
}
