# GHCR OCI label investigation

## Observations

The published `ghcr.io/adamcik/plan:main` config blob contains
`config.Labels.org.opencontainers.image.description`. This is the correct
location for a Docker-compatible OCI image label. GitHub documents this key as
package-page metadata for Container registry images.

The local image produced by the pinned `nix2container` input is valid when
copied to a `dir:` destination with its pinned Skopeo:

- the manifest contains five layers;
- the config contains five `rootfs.diff_ids`; and
- the config contains the description label.

The reported manifest from GHCR instead has a sixth descriptor: it duplicates
the config digest as an `application/octet-stream` layer. Such a descriptor is
not a valid OCI image layer, and its layer count does not match the config's
`rootfs.diff_ids` count. OCI defines manifest layers as filesystem changesets,
and the config's `rootfs.diff_ids` identifies those changesets.

## Upstream evidence

- GitHub supports `org.opencontainers.image.description` as a Container
  registry package description:
  <https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#labelling-container-images>
- OCI manifest and config specifications:
  <https://github.com/opencontainers/image-spec/blob/v1.1.1/manifest.md>
  <https://github.com/opencontainers/image-spec/blob/v1.1.1/config.md>
- nix2container issue [#127](https://github.com/nlewo/nix2container/issues/127)
  records GHCR/Skopeo publishing failures with inconsistent blobs. A later
  report in that issue says `skopeo copy --format v2s2` fixed the problem for
  that reporter. This is evidence for a format-sensitive transport issue, not
  proof that it fixes this image.
- The pinned nix2container custom `nix:` transport builds an OCI manifest from
  the image config and declared layers. Its source does not add the config as a
  layer:
  <https://github.com/nlewo/container-libs/blob/21b053ac62f3137de42585611953e923577d0e10/image/nix/transport.go>

## Next experiment

Publish the same build to a disposable GHCR tag while passing
`--format v2s2` to the existing `image.copyTo` command. Fetch the raw manifest
and config immediately after the push and assert:

1. the config contains the description label;
2. manifest layer count equals config `rootfs.diff_ids` count; and
3. the package page shows the description.

If the assertion passes, retain Docker schema 2 output for GHCR. If it fails,
compare the exact raw manifest uploaded by Skopeo with the one returned by
GHCR, then report the minimal reproduction upstream to nix2container/Skopeo.
