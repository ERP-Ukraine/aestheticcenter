#!/bin/bash

IMAGE="erpukraine/custom:${BITBUCKET_REPO_SLUG}-${O_MAJOR}.0-${BITBUCKET_BUILD_NUMBER}"
WITH_TEST_DB=${WITH_TEST_DB:-no}
WORKERS_COUNT=${WORKERS_COUNT:-2}

if [ $WITH_TEST_DB = "yes" ]; then
    VOLUME="/swarm/gv1/${BITBUCKET_REPO_SLUG}${O_MAJOR}-staging-data"
    SERVICE="${BITBUCKET_REPO_SLUG}-staging${O_MAJOR}"
    WORKERS_COUNT="0"
    unset DOMAIN
else
    VOLUME="/swarm/gv1/${BITBUCKET_REPO_SLUG}${O_MAJOR}-data"
    SERVICE="${BITBUCKET_REPO_SLUG}${O_MAJOR}"
fi

# Check if service exists
ssh bohdan@pve.erp.co.ua docker service ps ${SERVICE}

if [ $? -eq 0 ]; then
    echo "Updating service"
    ssh bohdan@pve.erp.co.ua docker service update --update-parallelism 1 --update-delay 15s --image ${IMAGE} ${SERVICE}
else
    echo "Creating service"
    ssh bohdan@pve.erp.co.ua "mkdir -p ${VOLUME} && sudo chown -R 101:101 ${VOLUME}"
    CREATE_SERVICE="docker service create \
        --tty \
        --with-registry-auth \
        --mount type=bind,src=${VOLUME},dst=/var/lib/odoo \
        --mount type=bind,src=/swarm/gv1/geoip,dst=/usr/share/GeoIP \
        --name ${SERVICE} \
        --network erpunet \
        --hostname=${SERVICE} \
        --secret gcp-service-account.json \
        --label traefik.docker.network=erpunet \
        --label traefik.enable=true \
        --label traefik.frontend.passHostHeader=true \
        --label traefik.backend.loadbalancer.swarm=true \
        --label traefik.backend.loadbalancer.method=drr \
        --label traefik.frontend.headers.SSLProxyHeaders='X-Forwarded-Proto:https' \
        "
    if [ $WITH_TEST_DB = "yes" ]; then
        CREATE_SERVICE+="\
            --label traefik.webtest.frontend.rule='Host:${BITBUCKET_REPO_SLUG}-staging.erp.co.ua' \
            --label traefik.webtest.frontend.redirect.regex='^(https://${BITBUCKET_REPO_SLUG}-staging.erp.co.ua/website/tests|https://${BITBUCKET_REPO_SLUG}-staging.erp.co.ua/website/info|https://${BITBUCKET_REPO_SLUG}-staging.erp.co.ua/web/database/[^l].*)' \
            --label traefik.webtest.frontend.redirect.replacement='https://${BITBUCKET_REPO_SLUG}-staging.erp.co.ua' \
            --label traefik.webtest.frontend.redirect.permanent=true \
            --label traefik.webtest.port=8069 \
            --label traefik.webtest.frontend.entryPoints=https \
            "
            if [ $WORKERS_COUNT != "0" ]; then
                CREATE_SERVICE+="\
                    --label traefik.polltest.frontend.rule='Host:${BITBUCKET_REPO_SLUG}-staging.erp.co.ua;PathPrefix:/longpolling/' \
                    --label traefik.polltest.port=8072 \
                    --label traefik.polltest.frontend.entryPoints=https \
                    "
            fi
    else
        CREATE_SERVICE+="\
        --label traefik.web.frontend.rule='Host:${BITBUCKET_REPO_SLUG}.erp.co.ua' \
        --label traefik.web.frontend.redirect.regex='^(https://${BITBUCKET_REPO_SLUG}.erp.co.ua/website/tests|https://${BITBUCKET_REPO_SLUG}.erp.co.ua/website/info|https://${BITBUCKET_REPO_SLUG}.erp.co.ua/web/database/[^l].*)' \
        --label traefik.web.frontend.redirect.replacement='https://${BITBUCKET_REPO_SLUG}.erp.co.ua' \
        --label traefik.web.frontend.redirect.permanent=true \
        --label traefik.web.port=8069 \
        --label traefik.web.frontend.entryPoints=https \
        "
         if [ $WORKERS_COUNT != "0" ]; then
                CREATE_SERVICE+="\
                    --label traefik.poll.frontend.rule='Host:${BITBUCKET_REPO_SLUG}.erp.co.ua;PathPrefix:/longpolling/' \
                    --label traefik.poll.port=8072 \
                    --label traefik.poll.frontend.entryPoints=https \
                    "
        fi
        # custom domain only for prod
        if [ -z ${DOMAIN+x} ]; then
            echo "Custom domain is not set"
        else
            CREATE_SERVICE+="\
                --label traefik.webdom.frontend.rule='Host:www.${DOMAIN},${DOMAIN}' \
                --label traefik.webdom.frontend.redirect.regex='^(https://${DOMAIN}/(.*)|https://www.${DOMAIN}/website/tests|https://www.${DOMAIN}/website/info|https://www.${DOMAIN}/web/database/[^l].*)' \
                --label traefik.webdom.frontend.redirect.replacement='https://www.${DOMAIN}/\$2' \
                --label traefik.webdom.frontend.redirect.permanent=true \
                --label traefik.webdom.port=8069 \
                --label traefik.webdom.frontend.entryPoints=https \
                "
                if [ $WORKERS_COUNT != "0" ]; then
                    CREATE_SERVICE+="\
                        --label traefik.polldom.frontend.rule='Host:www.${DOMAIN};PathPrefix:/longpolling/' \
                        --label traefik.polldom.port=8072 \
                        --label traefik.polldom.frontend.entryPoints=https \
                        "
                fi
        fi
    fi
    CREATE_SERVICE+=" ${IMAGE}"
    ssh bohdan@pve.erp.co.ua "docker image pull ${IMAGE}"
    ssh bohdan@pve.erp.co.ua $CREATE_SERVICE

    # if [ $? -eq 0 ]; then
    #     echo "Init database"
    #     CONTAINERID=`ssh bohdan@pve.erp.co.ua "docker ps --filter name=${SERVICE} -q"`
    #     ssh bohdan@pve.erp.co.ua "docker exec -u odoo -i ${CONTAINERID} \
    #         odoo --no-http --stop-after-init --load-language en_US,uk_UA -i base,web -d odoo${O_MAJOR}-${BITBUCKET_REPO_SLUG}"
    #     if [ $WITH_TEST_DB = "yes" ]; then
    #         ssh bohdan@pve.erp.co.ua "docker exec -u odoo -i ${CONTAINERID} \
    #             odoo --no-http --stop-after-init --load-language en_US,uk_UA -i base,web -d odoo${O_MAJOR}-${BITBUCKET_REPO_SLUG}test"
    #     fi
    # fi
fi

ssh bohdan@pve.erp.co.ua docker service logs ${SERVICE} --since=1m --raw
