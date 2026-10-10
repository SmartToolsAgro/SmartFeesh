#!/usr/bin/env bash
# Deploys the committed HEAD to staging: `make deploy-staging` (or the CI job on main).
# Sends a copy of the code (git archive, so nothing uncommitted) and runs remote-deploy.sh on the server.
set -euo pipefail

TARGET="${DEPLOY_TARGET:-debian@217.182.205.137}"
SSH_OPTS=(${DEPLOY_SSH_OPTS:-})
RELEASE="$(date -u +%Y%m%d%H%M%S)-$(git rev-parse --short HEAD)"
REMOTE_DIR="frutti-staging/releases/$RELEASE"

echo "Deploying $RELEASE to $TARGET"
git archive --format=tar HEAD | ssh "${SSH_OPTS[@]}" "$TARGET" "mkdir -p $REMOTE_DIR && tar -x -C $REMOTE_DIR"
ssh "${SSH_OPTS[@]}" "$TARGET" "bash $REMOTE_DIR/deploy/remote-deploy.sh $RELEASE"
