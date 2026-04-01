# Go targets
.PHONY: go-build go-test go-run go-vet go-tidy

go-tidy:
	go mod tidy

go-build: go-tidy
	go build -o ./bin/morphic ./cmd/morphic

go-test:
	go test ./...

go-vet:
	go vet ./...

go-run: go-build
	./bin/morphic
