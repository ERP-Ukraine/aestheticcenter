#!/bin/sh
# Setup envirinment

mkdir -p ~/.ssh
echo $KNOWN_PVE | base64 --decode >> ~/.ssh/known_hosts
(umask  077 ; echo $SSH_KEY | base64 --decode > ~/.ssh/id_rsa)
(echo $DOCKER_PASSWORD | docker login --username $DOCKER_USERNAME --password-stdin)
echo "Environment configured"

# Use Ansible config via env vars because build dir is writable
export ANSIBLE_PYTHON_INTERPRETER="auto_legacy_silent"
export ANSIBLE_TRANSPORT="ssh"
