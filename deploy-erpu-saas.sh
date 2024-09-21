#!/bin/sh

set -e

if [ "$ERPUSAAS_DEPLOY_SECRET" != "" ]; then
    echo "ERPU SaaS Deploy"
    if [ "$1" = "production" ]; then
        curl --fail -X POST \
            -F 'token=$ERPUSAAS_DEPLOY_SECRET' \
            -F 'commit=$BITBUCKET_COMMIT' \
            -F 'build=$BITBUCKET_BUILD_NUMBER' \
            https://erp.co.ua/erpusaas/project/${ERPUSAAS_DEPLOY_PROJECT}/production/rebuild
    fi
    if [ "$1" = "staging1" ]; then
        curl --fail -X POST \
            -F 'token=$ERPUSAAS_DEPLOY_SECRET' \
            -F 'commit=$BITBUCKET_COMMIT' \
            -F 'build=$BITBUCKET_BUILD_NUMBER' \
            https://erp.co.ua/erpusaas/project/${ERPUSAAS_DEPLOY_PROJECT}/staging1/rebuild
    fi
else
    echo "Ansible Deploy"
    if [ "$1" = "production" ]; then
        ./setup.sh
        ansible-playbook deploy-prod.yml -i "$PVE_DOMAIN," \
            -e O_MAJOR=$O_MAJOR \
            -e BITBUCKET_BUILD_NUMBER=$BITBUCKET_BUILD_NUMBER \
            -e BITBUCKET_REPO_SLUG=$BITBUCKET_REPO_SLUG \
            -e DOCKER_USERNAME=$DOCKER_USERNAME \
            -e DOCKER_PASSWORD=$DOCKER_PASSWORD \
            -e WORKERS_COUNT=${WORKERS_COUNT:-1} \
            -e DOMAIN=$DOMAIN \
            -e DOMAIN2=$DOMAIN2 \
            -e DOMAIN3=$DOMAIN3 \
            -e DOMAIN4=$DOMAIN4 \
            -e DOMAIN5=$DOMAIN5 \
            -e DOMAIN6=$DOMAIN6 \
            -e DOMAIN7=$DOMAIN7 \
            -e NAKED_DOMAIN=$NAKED_DOMAIN
    fi
    if [ "$1" = "staging1" ]; then
        export WITH_TEST_DB="yes"
        ./setup.sh
        ansible-playbook deploy-prod.yml -i "$PVE_DOMAIN," \
            -e O_MAJOR=$O_MAJOR \
            -e BITBUCKET_BUILD_NUMBER=$BITBUCKET_BUILD_NUMBER \
            -e BITBUCKET_REPO_SLUG=$BITBUCKET_REPO_SLUG \
            -e DOCKER_USERNAME=$DOCKER_USERNAME \
            -e DOCKER_PASSWORD=$DOCKER_PASSWORD \
            -e WORKERS_COUNT=1 \
            -e WITH_TEST_DB="yes"
    fi
fi
