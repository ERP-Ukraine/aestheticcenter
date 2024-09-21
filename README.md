# saas-template

Environment variables on repository level.

- `O_MAJOR` - Odoo major version: 16, 15, 14, ...
- `ERPUSAAS_DEPLOY_PROJECT` - ERPU SaaS Project ID: integer
- `ERPUSAAS_DEPLOY_SECRET` - ERPU SaaS Project Deploy Secret: string

Ansible deploy variables:

- `O_EDITION` - ee or ce edition. Default ee.
- `SAAS_RELEASE` - Odoo release version of SaaS image. Default to `O_RELEASE`.
- `WORKERS_COUNT` - number of scaled docker services. Default 1.
- `DOMAIN` - set custom domain. It has to be configured with CNAME reference before enabling here.
- `NAKED_DOMAIN` - if set will add redirect from `NAKED_DOMAIN` to `DOMAIN`.
- `DOMAIN2` .. `DOMAIN7` - set extra custom domains.

Create staging branch to deploy staging service.
