# Kodi under a virtual X display, for e2e/run.sh.
#   Kodi 21 (Omega):  BASE=debian:trixie (default)
#   Kodi 19 (Matrix): BASE=ubuntu:22.04
ARG BASE=debian:trixie
FROM ${BASE}
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends kodi xvfb xauth x11-utils imagemagick ffmpeg python3 curl \
      ca-certificates libgl1-mesa-dri mesa-utils openssl procps xdotool tzdata \
 && rm -rf /var/lib/apt/lists/*
RUN useradd -m viewer
