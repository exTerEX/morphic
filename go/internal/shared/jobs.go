package shared

import (
	"sync"
	"time"

	"github.com/google/uuid"
)

// JobStatus represents the state of a background job.
type JobStatus string

const (
	JobStatusPending JobStatus = "pending"
	JobStatusRunning JobStatus = "running"
	JobStatusDone    JobStatus = "done"
	JobStatusFailed  JobStatus = "failed"
	JobStatusPlanned JobStatus = "planned"
)

// Job is a base type embedded in all module-specific jobs.
type Job struct {
	ID        string    `json:"id"`
	Status    JobStatus `json:"status"`
	Progress  float64   `json:"progress"`
	Message   string    `json:"message,omitempty"`
	Error     string    `json:"error,omitempty"`
	StartedAt time.Time `json:"started_at"`
	DoneAt    time.Time `json:"done_at,omitempty"`
}

// NewJob creates a new job with a unique ID.
func NewJob() Job {
	return Job{
		ID:        uuid.New().String(),
		Status:    JobStatusPending,
		Progress:  0,
		StartedAt: time.Now(),
	}
}

// JobStore is a thread-safe generic store for background jobs.
type JobStore[T any] struct {
	mu   sync.RWMutex
	jobs map[string]*T
}

// NewJobStore creates a new JobStore.
func NewJobStore[T any]() *JobStore[T] {
	return &JobStore[T]{
		jobs: make(map[string]*T),
	}
}

// Set stores a job.
func (s *JobStore[T]) Set(id string, job *T) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.jobs[id] = job
}

// Get retrieves a job by ID.
func (s *JobStore[T]) Get(id string) (*T, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	job, ok := s.jobs[id]
	return job, ok
}

// Delete removes a job by ID.
func (s *JobStore[T]) Delete(id string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	delete(s.jobs, id)
}

// StartCleanup runs a background goroutine that removes jobs older than ttl.
func (s *JobStore[T]) StartCleanup(ttl time.Duration, getDoneAt func(*T) time.Time) {
	go func() {
		ticker := time.NewTicker(ttl / 2)
		defer ticker.Stop()
		for range ticker.C {
			now := time.Now()
			s.mu.Lock()
			for id, job := range s.jobs {
				doneAt := getDoneAt(job)
				if !doneAt.IsZero() && now.Sub(doneAt) > ttl {
					delete(s.jobs, id)
				}
			}
			s.mu.Unlock()
		}
	}()
}
