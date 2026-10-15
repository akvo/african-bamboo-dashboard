# Tests run in the build stage, so a failing test fails the build and
# no Go install is needed on the host.
FROM golang:1.23-alpine AS build
WORKDIR /src
COPY go.mod *.go ./
RUN go test ./... && CGO_ENABLED=0 go build -ldflags="-s -w" -o /kobo-mock .

FROM scratch
COPY --from=build /kobo-mock /kobo-mock
USER 65534:65534
EXPOSE 8090
ENTRYPOINT ["/kobo-mock"]
