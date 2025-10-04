#!/usr/bin/env bash
set -o errexit

export $(cat .env | xargs)

git submodule init
git submodule update --remote
export REPO="erpukraine/custom" PROJECT="${BITBUCKET_REPO_SLUG}" VERSION="v1.0"
if [[ -v BITBUCKET_BUILD_NUMBER ]]; then VERSION=${BITBUCKET_BUILD_NUMBER}; fi
export IMAGE_NAME=${REPO}:${PROJECT}-${VERSION}
export UPDATED_MODULES=`ls ./extra-addons/ | awk -vORS=, '{ print $1 }' | sed 's/,$/\n/'`
if [ -z ${UPDATED_MODULES} ]; then echo "Nothing to test"; exit 0; fi
echo "Testing ${UPDATED_MODULES}"
echo $DOCKER_PASSWORD | docker login --username $DOCKER_USERNAME --password-stdin
sed -i -e 's/without_demo = True/without_demo = False/g' odoo.conf
sed -i -e 's/use_redis = .*/use_redis = False/g' odoo.conf
sed -i -e "s/db_host =.*/db_host = host.docker.internal/g" odoo.conf
docker build --build-arg SAAS_IMG=erpukraine/odoo-ee-erpu-saas:${O_MAJOR}.0-latest -t ${IMAGE_NAME} .
mkdir ${BITBUCKET_CLONE_DIR}/data && chmod 777 ${BITBUCKET_CLONE_DIR}/data
docker run --rm -t --name=${PROJECT}-${VERSION} \
    --add-host host.docker.internal:${BITBUCKET_DOCKER_HOST_INTERNAL} \
    -v ${BITBUCKET_CLONE_DIR}/data:/var/lib/odoo \
    -e "HOST=host.docker.internal" ${IMAGE_NAME} \
    -i base,web,${UPDATED_MODULES} -d test-db \
    --db_host=host.docker.internal --db-filter=test-db \
    -w odoo -r odoo --workers=0 --stop-after-init
docker run --rm -t --name=${PROJECT}-${VERSION} \
    --add-host host.docker.internal:${BITBUCKET_DOCKER_HOST_INTERNAL} \
    -v ${BITBUCKET_CLONE_DIR}/data:/var/lib/odoo -e "HOST=host.docker.internal" \
    -e "COVERAGE_FILE=/tmp/.coverage" -e "MARICHKA_KEY=${MARICHKA_KEY}" ${IMAGE_NAME} \
    /bin/bash -c "set -e; coverage run /usr/bin/odoo \
    -u ${UPDATED_MODULES} --workers=0 -d test-db --stop-after-init --test-enable -w odoo -r odoo \
    --test-tags standard,external,post_install_l10n \
    --db_host host.docker.internal --db-filter=test-db; coverage report \
    --omit */system_site_packages/*,*/site-packages/*,*/dist-packages/*,*/pyshared/*,*/enterprise-addons/* "
