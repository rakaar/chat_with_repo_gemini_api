FROM python:3.10.14-bullseye

RUN apt-get update && \
  apt-get install -y \
  locales \
  locales-all && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

ENV LC_ALL=en_US.UTF-8
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US.UTF-8

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Create non-root user
RUN groupadd -g 900 mesop && useradd -u 900 -s /bin/bash -g mesop mesop

# Add app code here
COPY . /srv/mesop-app
WORKDIR /srv/mesop-app

# Create the repository directory and set permissions
RUN mkdir -p /srv/mesop-app/repo && chown -R mesop:mesop /srv/mesop-app/repo

# Switch to non-root user
USER mesop

# Run Mesop through gunicorn. Should be available at localhost:8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "300", "main:me"]

