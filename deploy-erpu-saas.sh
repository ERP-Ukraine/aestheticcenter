#!/bin/sh

# Deploy script for ERPU SaaS
# Usage: ./deploy-erpu-saas.sh <production|staging1>

set -e

# Configuration
readonly API_BASE_URL="${ERPUSAAS_API_URL:-https://erp.co.ua}"
readonly MAX_WAIT_ATTEMPTS=60
readonly POLL_INTERVAL=5

# Check dependencies
for cmd in curl jq; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "Error: Required command '$cmd' not found" >&2
        exit 1
    fi
done

wait_for_build() {
    local build_id="$1"
    local token="$2"

    [ -z "$build_id" ] && { echo "Error: build_id is empty" >&2; return 1; }

    for i in $(seq 1 "$MAX_WAIT_ATTEMPTS"); do
        response=$(curl --fail -s -H "Authorization: Bearer $token" \
            "$API_BASE_URL/erpusaas/build/${build_id}/status") || {
            echo "✗ Error: HTTP request failed" >&2
            return 3
        }

        state=$(echo "$response" | jq -r '.state')
        display_name=$(echo "$response" | jq -r '.display_name')

        echo "[$i/$MAX_WAIT_ATTEMPTS] $display_name - $state"

        case "$state" in
            running)
                echo "✓ Build is running!"
                return 0
                ;;
            failed)
                echo "✗ Build failed!" >&2
                return 1
                ;;
        esac

        sleep "$POLL_INTERVAL"
    done

    echo "⏱ Timeout: Build did not complete within $((MAX_WAIT_ATTEMPTS * POLL_INTERVAL)) seconds" >&2
    return 2
}

trigger_rebuild() {
    local env="$1"
    curl --fail -s -X POST \
        -F "token=$ERPUSAAS_DEPLOY_SECRET"  \
        -F "commit=$BITBUCKET_COMMIT" \
        -F "build=$BITBUCKET_BUILD_NUMBER" \
        "$API_BASE_URL/erpusaas/project/${ERPUSAAS_DEPLOY_PROJECT}/${env}/rebuild"
}

# Validate input
if [ $# -ne 1 ]; then
    echo "Usage: $0 <production|staging1>" >&2
    exit 1
fi

environment="$1"
case "$environment" in
    production|staging1) ;;
    *)
        echo "Error: Invalid environment '$environment'. Must be 'production' or 'staging1'" >&2
        exit 1
        ;;
esac

if [ -n "$ERPUSAAS_DEPLOY_SECRET" ]; then
    echo "ERPU SaaS Deploy to $environment"

    BUILD_ID=$(trigger_rebuild "$environment")
    if [ -z "$BUILD_ID" ]; then
        echo "Error: Failed to trigger rebuild" >&2
        exit 1
    fi

    wait_for_build "$BUILD_ID" "$ERPUSAAS_DEPLOY_SECRET"
    exit $?
else
    echo "Ansible Deploy to $environment"

    # Check ansible dependency
    if ! command -v ansible-playbook >/dev/null 2>&1; then
        echo "Error: ansible-playbook not found" >&2
        exit 1
    fi

    if [ "$environment" = "staging1" ]; then
        export WITH_TEST_DB="yes"
    fi

    ./setup.sh

    ansible-playbook deploy-prod.yml -i "$PVE_DOMAIN," \
        -e "O_MAJOR=$O_MAJOR" \
        -e "BITBUCKET_BUILD_NUMBER=$BITBUCKET_BUILD_NUMBER" \
        -e "BITBUCKET_REPO_SLUG=$BITBUCKET_REPO_SLUG" \
        -e "DOCKER_USERNAME=$DOCKER_USERNAME" \
        -e "DOCKER_PASSWORD=$DOCKER_PASSWORD" \
        -e "WORKERS_COUNT=${WORKERS_COUNT:-1}" \
        ${environment:+"staging1" && echo '-e "WITH_TEST_DB=yes"'} \
        $([ "$environment" = "production" ] && cat <<-EOF
        -e "DOMAIN=$DOMAIN" \
        -e "DOMAIN2=$DOMAIN2" \
        -e "DOMAIN3=$DOMAIN3" \
        -e "DOMAIN4=$DOMAIN4" \
        -e "DOMAIN5=$DOMAIN5" \
        -e "DOMAIN6=$DOMAIN6" \
        -e "DOMAIN7=$DOMAIN7" \
        -e "NAKED_DOMAIN=$NAKED_DOMAIN"
EOF
        )
fi
