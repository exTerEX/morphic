# Go targets
.PHONY: build test run vet tidy

tidy:
	go mod tidy

build: tidy
	go build -o ./bin/morphic ./cmd/morphic

test:
	go test ./...

vet:
	go vet ./...

run: build
	./bin/morphic
