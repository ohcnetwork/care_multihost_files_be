# CARE multihost files

A CARE backend plugin that makes file uploads and downloads work when one CARE
installation is reached under more than one address.

## The problem

CARE builds file links from a single fixed setting, `BUCKET_EXTERNAL_ENDPOINT`.
When the same CARE is reached under several addresses, for example
`https://care.local` on the clinic network and
`https://clinic.tail1234.ts.net:8443` through Tailscale from home, every page and
API call works under both, but file links always point at the one configured
address. From the other address, files do not open and uploads fail.

The links are signed (S3 presigned URLs), and the signature covers the address,
so the link cannot simply be rewritten after it is made.

## What the plugin does

1. When a request starts, it notes the address the request came in on
   (`X-Forwarded-Host`, otherwise `Host`), if that address is on the allowed list.
2. While that request runs, CARE's file links are built and signed for that
   address instead of the fixed one:
   - signed download and upload links (`get_facility_bucket_config`,
     `get_patient_bucket_config` and `get_report_bucket_config` with `external=True`);
   - facility cover images (`Facility.read_cover_image_url`);
   - user profile pictures (`User.read_profile_picture_url`).
3. Everything else keeps today's behaviour: requests from addresses not on the
   list, work without a request (Celery tasks), internal storage access, and
   storage that is not served behind an allowed address, such as Amazon S3 or a CDN.

No CARE source file changes. The plugin wraps those functions when Django starts.

## When you need it

- File storage (MinIO, Silo or similar) is served behind the same address as CARE,
  through a reverse proxy, and
- CARE is reached under more than one address: LAN and VPN, an internal and a
  public domain, an old and a new domain, and so on.

You do not need it when files are served from a cloud provider's own address,
or when CARE has only one address.

## Configuration

| Setting | Meaning | Example |
| --- | --- | --- |
| `ALLOWED_HOSTS` | Address patterns that file links may use. Matched against the host name without its port, case-insensitively, with `*` wildcards. Empty means the plugin changes nothing. | `["*.local", "*.ts.net"]` |

Set it in the plugin's `configs`, or with the environment variable
`MULTIHOST_FILES_ALLOWED_HOSTS` (comma-separated or a JSON list).

Both the address a request comes in on and the address of the configured file
storage must match the list for a link to change. A forged `Host` header for an
address outside the list therefore never changes a link.

## Installing

Add it to `ADDITIONAL_PLUGS` and rebuild the backend image:

```json
[
  {
    "name": "care_multihost_files",
    "package_name": "git+https://github.com/praffq/care_multihost_files.git",
    "version": "@main",
    "configs": {"ALLOWED_HOSTS": ["*.local", "*.ts.net"]}
  }
]
```

Your reverse proxy must pass the original address through to both the backend
and file storage (Caddy and nginx do this by default for `Host`), so storage
checks the signature against the same address the link was signed for.

## Development

Tests run with Django and need no CARE checkout:

```bash
python -m unittest discover -s tests -t .
```

The wrapped functions are internal to CARE. If CARE renames or reshapes them,
the plugin logs a warning at startup and those links keep their usual address.
Run the tests against each CARE version you deploy.
