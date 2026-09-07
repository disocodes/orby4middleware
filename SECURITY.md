# Security

orby4middleware handles clinical data and must be deployed on trusted healthcare networks with TLS,
strong secrets, network segmentation, least-privilege access, encrypted backups, and local regulatory
controls. Never expose analyzer serial/TCP listeners directly to the public internet.

Report security issues privately to the repository owner. Do not place patient data, production
credentials, analyzer captures containing identifiers, or private keys in GitHub issues.

## Clinical safety boundary

orby4middleware is interoperability software, not a diagnostic device. A site must validate each
analyzer/model/profile before enabling automatic result delivery. Unmatched results are held rather
than attached to a patient by name or fuzzy matching.
