#!/bin/sh

if [ "$ERPUSAAS_DEPLOY_SECRET" != "" ]; then
    echo "ERPU SaaS deploy enabled. Exiting..."
    exit 0
fi

set -e

export $(cat .env | xargs)

# Compute base image
REPO="erpukraine/odoo-ee-erpu-saas"
IMAGE_TAG="${O_MAJOR}.0"
if [ $O_EDITION = "ce" ]; then
    REPO="erpukraine/odoo-erpu-saas"
fi
SAAS_IMG=${REPO}:${IMAGE_TAG}-${SAAS_RELEASE}

IMAGE="erpukraine/custom:${BITBUCKET_REPO_SLUG}-${O_MAJOR}.0-${BITBUCKET_BUILD_NUMBER}"

WITH_TEST_DB=${WITH_TEST_DB:-no}

git submodule init
git submodule update --remote

sed -i -e "s/without_demo =.*/without_demo = True/g" odoo.conf
sed -i -e "s/^admin_passwd.*/admin_passwd = ${ADMIN_PASSWORD}/" odoo.conf
if [ $O_MAJOR -gt "15" ]; then
    sed -i -e "s/^db_host.*/db_host = ${DB_HOST13}/" odoo.conf
else
    sed -i -e "s/^db_host.*/db_host = ${DB_HOST}/" odoo.conf
fi
sed -i -e "s/^db_user.*/db_user = ${DB_USER}/" odoo.conf
sed -i -e "s/^db_port.*/db_port = ${DB_PORT}/" odoo.conf
sed -i -e "s/^db_password.*/db_password = ${DB_PASSWORD}/" odoo.conf
if [ $WITH_TEST_DB = "yes" ]; then
    WORKERS_COUNT="0"
    sed -i -e "s/^db_name.*/db_name = odoo${O_MAJOR}-${BITBUCKET_REPO_SLUG}-staging/" odoo.conf
    sed -i -e "s/^dbfilter.*/dbfilter = ^odoo${O_MAJOR}-${BITBUCKET_REPO_SLUG}-staging$/" odoo.conf
else
    sed -i -e "s/^db_name.*/db_name = odoo${O_MAJOR}-${BITBUCKET_REPO_SLUG}/" odoo.conf
    sed -i -e "s/^dbfilter.*/dbfilter = ^odoo${O_MAJOR}-${BITBUCKET_REPO_SLUG}$/" odoo.conf
fi
sed -i -e "s/^workers.*/workers = 0/" odoo.conf
sed -i -e "s/^log_influxdb =.*/log_influxdb = True/" odoo.conf
sed -i -e "s/^log_influxdb_user.*/log_influxdb_user = ${INFLUXDB_USER}/" odoo.conf
sed -i -e "s/^log_influxdb_password.*/log_influxdb_password = ${INFLUXDB_USER_PASSWORD}/" odoo.conf

docker build --no-cache --build-arg SAAS_IMG=${SAAS_IMG} -t ${IMAGE} . && \
docker push  ${IMAGE} && \
echo "${IMAGE} has been built and pushed."
