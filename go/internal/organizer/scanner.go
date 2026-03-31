package organizer

import (
	"sync"
	"time"

	"github.com/exterex/morphic/internal/shared"
)

// ScanJob represents an organizer scan/plan/execute job.
type ScanJob struct {
	shared.Job
	mu sync.Mutex

	Folder      string            `json:"folder"`
	Phase       string            `json:"phase"`
	ScanType    string            `json:"scan_type"`
	Template    string            `json:"template"`
	Destination string            `json:"destination"`
	Operation   string            `json:"operation"`
	Mode        string            `json:"mode"`
	Files       []string          `json:"files,omitempty"`
	SortPlan    []SortPlanEntry   `json:"sort_plan,omitempty"`
	RenamePlan  []RenamePlanEntry `json:"rename_plan,omitempty"`
	Total       int               `json:"total"`
	Processed   int               `json:"processed"`
}

var store = shared.NewJobStore[ScanJob]()

func init() {
	store.StartCleanup(30*time.Minute, func(j *ScanJob) time.Time {
		return j.DoneAt
	})
}

// StartPlanJob starts a new planning job.
func StartPlanJob(folder, mode, template, destination, operation, scanType string) string {
	job := &ScanJob{
		Job:         shared.NewJob(),
		Folder:      folder,
		Phase:       "scanning",
		Mode:        mode,
		Template:    template,
		Destination: destination,
		Operation:   operation,
		ScanType:    scanType,
	}
	job.Status = shared.JobStatusRunning

	store.Set(job.ID, job)

	go runPlan(job)

	return job.ID
}

// GetJob retrieves a job by ID.
func GetJob(id string) (*ScanJob, bool) {
	return store.Get(id)
}

// ExecuteJob starts the execution phase of a planned job.
func ExecuteJob(id string) bool {
	job, ok := store.Get(id)
	if !ok || job.Phase != "planned" {
		return false
	}

	job.mu.Lock()
	job.Phase = "executing"
	job.Progress = 0
	job.Processed = 0
	job.mu.Unlock()

	go runExecute(job)
	return true
}

func runPlan(job *ScanJob) {
	var files []shared.FileInfo
	var err error

	switch job.ScanType {
	case "images":
		files, err = shared.FindImageFiles(job.Folder)
	case "videos":
		files, err = shared.FindVideoFiles(job.Folder)
	default:
		files, err = shared.FindAllMediaFiles(job.Folder)
	}

	if err != nil {
		job.mu.Lock()
		job.Status = shared.JobStatusFailed
		job.Error = err.Error()
		job.DoneAt = time.Now()
		job.mu.Unlock()
		return
	}

	paths := make([]string, len(files))
	for i, f := range files {
		paths[i] = f.Path
	}

	job.mu.Lock()
	job.Files = paths
	job.Total = len(paths)
	job.Phase = "planning"
	job.Progress = 0.3
	job.mu.Unlock()

	switch job.Mode {
	case "sort":
		dest := job.Destination
		if dest == "" {
			dest = job.Folder
		}
		plan := PlanSort(paths, job.Template, dest)
		job.mu.Lock()
		job.SortPlan = plan
		job.mu.Unlock()
	case "rename":
		plan := PlanRename(paths, job.Template, job.Operation)
		job.mu.Lock()
		job.RenamePlan = plan
		job.mu.Unlock()
	}

	job.mu.Lock()
	job.Phase = "planned"
	job.Progress = 1.0
	job.Message = "Plan ready for review"
	job.mu.Unlock()
}

func runExecute(job *ScanJob) {
	switch job.Mode {
	case "sort":
		ExecuteSort(job.SortPlan, job.Operation)
		job.mu.Lock()
		for _, e := range job.SortPlan {
			if e.Status == "done" {
				job.Processed++
			}
		}
		job.mu.Unlock()
	case "rename":
		ExecuteRename(job.RenamePlan, job.Operation)
		job.mu.Lock()
		for _, e := range job.RenamePlan {
			if e.Status == "done" {
				job.Processed++
			}
		}
		job.mu.Unlock()
	}

	job.mu.Lock()
	job.Phase = "done"
	job.Status = shared.JobStatusDone
	job.Progress = 1.0
	job.DoneAt = time.Now()
	job.mu.Unlock()
}
