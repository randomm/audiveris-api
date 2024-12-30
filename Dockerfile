# syntax=docker/dockerfile:1.4
FROM eclipse-temurin:21-jdk as builder

# Build arguments
ARG CACHEBUST=1
ARG AUDIVERIS_VERSION=5.4-alpha-3

# Update package list and install build dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    rm -rf /var/lib/apt/lists/* && \
    apt-get update && \
    apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set up Audiveris build environment
WORKDIR /app/audiveris

# Clone and build Audiveris
RUN --mount=type=cache,target=/root/.gradle,sharing=locked \
    git clone https://github.com/Audiveris/audiveris.git . && \
    git checkout ${AUDIVERIS_VERSION} && \
    ./gradlew build -x test && \
    cd app/build/distributions && \
    tar xf app-*.tar && \
    mkdir -p /opt/audiveris && \
    mv app-*/* /opt/audiveris/

# Final image
FROM eclipse-temurin:21-jdk

# Install runtime dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    rm -rf /var/lib/apt/lists/* && \
    apt-get update && \
    apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    libleptonica-dev \
    libfreetype6 \
    imagemagick \
    python3-full \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Configure ImageMagick policy to increase resource limits
RUN sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/' /etc/ImageMagick-6/policy.xml && \
    sed -i 's/<policy domain="resource" name="memory" value="256MiB"\/>/<policy domain="resource" name="memory" value="2GiB"\/>/g' /etc/ImageMagick-6/policy.xml && \
    sed -i 's/<policy domain="resource" name="disk" value="1GiB"\/>/<policy domain="resource" name="disk" value="4GiB"\/>/g' /etc/ImageMagick-6/policy.xml

# Copy Audiveris from builder
COPY --from=builder /opt/audiveris /opt/audiveris

# Create a directory for input/output files
RUN mkdir -p /data

# Create Audiveris CLI script
RUN echo '#!/bin/sh\n\
java -Xmx1g -cp "/opt/audiveris/lib/*" Audiveris -batch "$@"' > /usr/local/bin/audiveris && \
    chmod +x /usr/local/bin/audiveris

# Set up Python environment
WORKDIR /app/api

# Install Python dependencies from requirements.txt
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    python3 -m pip install --break-system-packages -r requirements.txt

# Copy API code and entry script last (changes most frequently)
COPY . .
COPY audiveris-entry.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /data
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["api"]