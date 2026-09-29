FROM golang:1.24-alpine AS builder

ARG MC_REF=RELEASE.2025-08-13T08-35-41Z

RUN apk add --no-cache \
    git \
    ca-certificates

RUN git clone \
    --depth 1 \
    --branch "${MC_REF}" \
    https://github.com/minio/mc.git \
    /src/mc

WORKDIR /src/mc

ENV CGO_ENABLED=0

RUN go build \
    -trimpath \
    -ldflags="-s -w" \
    -o /out/mc \
    .

FROM alpine:3.22

RUN apk add --no-cache ca-certificates

COPY --from=builder /out/mc /usr/local/bin/mc

RUN chmod 0755 /usr/local/bin/mc

ENTRYPOINT ["/usr/local/bin/mc"]
