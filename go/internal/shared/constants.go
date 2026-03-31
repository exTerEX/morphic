package shared

const Version = "0.1.0"

const (
	DefaultImageThreshold = 0.90
	DefaultVideoThreshold = 0.85
	DefaultHashSize       = 16
	DefaultNumFrames      = 10
	DefaultNumWorkers     = 4
	DefaultBatchSize      = 1000
)

// ImageExtensions contains all supported image file extensions (lowercase, with dot prefix).
var ImageExtensions = map[string]struct{}{
	".jpg":  {},
	".jpeg": {},
	".png":  {},
	".tif":  {},
	".tiff": {},
	".bmp":  {},
	".webp": {},
	".gif":  {},
	".ico":  {},
	".heic": {},
	".heif": {},
	".avif": {},
	".svg":  {},
	".raw":  {},
	".cr2":  {},
	".nef":  {},
	".arw":  {},
	".dng":  {},
	".orf":  {},
	".rw2":  {},
	".pef":  {},
	".srw":  {},
}

// VideoExtensions contains all supported video file extensions.
var VideoExtensions = map[string]struct{}{
	".mp4":  {},
	".mov":  {},
	".avi":  {},
	".mkv":  {},
	".webm": {},
	".flv":  {},
	".wmv":  {},
	".m4v":  {},
	".mpeg": {},
	".mpg":  {},
	".3gp":  {},
	".ts":   {},
	".ogv":  {},
	".mts":  {},
	".m2ts": {},
	".vob":  {},
	".divx": {},
	".xvid": {},
	".asf":  {},
	".rm":   {},
	".rmvb": {},
}

// ExcludedFolders contains folder names to skip during scanning.
var ExcludedFolders = map[string]struct{}{
	// Windows
	"$recycle.bin":              {},
	"$recycle":                  {},
	"recycler":                  {},
	"recycled":                  {},
	"system volume information": {},
	"windows":                   {},
	"appdata":                   {},
	// macOS
	".trash":          {},
	".trashes":        {},
	".spotlight-v100": {},
	".fseventsd":      {},
	".ds_store":       {},
	// Linux
	"lost+found": {},
	"trash":      {},
	// Thumbnails
	".thumbnails": {},
	".thumb":      {},
	"thumbs":      {},
	// NAS
	"@eadir": {},
	// Version control
	".git": {},
	".svn": {},
	".hg":  {},
	// Development
	"__pycache__":  {},
	".cache":       {},
	"node_modules": {},
	".venv":        {},
	"venv":         {},
}

// Aliases maps alternative extensions to their canonical form.
var Aliases = map[string]string{
	".jpeg": ".jpg",
	".tiff": ".tif",
	".mpg":  ".mpeg",
}
