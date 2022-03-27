# saas-template

Environment variables on repository level.

- `O_MAJOR` - Odoo major version: 15, 14, ...
- `O_EDITION` - ee or ce edition. Default ee.
- `SAAS_RELEASE` - Odoo release version of SaaS image. Default to `O_RELEASE`.
- `WORKERS_COUNT` - number of scaled docker services. Default 1.
- `DOMAIN` - set custom domain. It has to be configured with CNAME reference before enabling here.

Create staging branch to deploy staging service.
