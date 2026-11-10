#!/usr/bin/env bash
# Attaches finished downloads to the public release "v<VERSION>" (the release the website links to as "latest").
#
# windows.yml and android.yml run on their own and each call this for their own file:
#     bash publish-release.sh artifacts/RoutePou-android.apk
# so the two never wait for each other, and a failed build of one does not hold back the other.
#
# Needs: git, the GitHub CLI (gh), GH_TOKEN, GITHUB_SHA, and a checkout of the repository.
set -euo pipefail

[ "$#" -gt 0 ] || { echo "usage: bash publish-release.sh FILE..." >&2; exit 2; }
version="$(tr -d '[:space:]' < VERSION)"
tag="v${version}"
sha="${GITHUB_SHA:-$(git rev-parse HEAD)}"
notes="$(mktemp)"

assets=()
for file in "$@"; do
  [ -s "$file" ] || { echo "::error::$file is missing or empty, nothing to publish"; exit 1; }
  dir="$(dirname "$file")"; name="$(basename "$file")"
  ( cd "$dir" && sha256sum "$name" > "$name.sha256" )
  assets+=("$file" "$file.sha256")
done

bash release-notes.sh > "$notes"

# Move the version tag to the commit that was built, so the release, its source archive and the files attached
# to it all describe the same build. (Both workflows do this; for one commit the result is identical.)
git tag -f "$tag" "$sha"
git push -f origin "refs/tags/$tag"

if gh release view "$tag" > /dev/null 2>&1; then
  gh release edit "$tag" --title "RoutePou ${version}" --notes-file "$notes" --draft=false --prerelease=false --latest
else
  # The other workflow may create the release at the same moment: if ours loses that race, carry on.
  gh release create "$tag" --verify-tag --title "RoutePou ${version}" --notes-file "$notes" --latest \
    || gh release view "$tag" > /dev/null
fi

gh release upload "$tag" "${assets[@]}" --clobber
echo "Published: ${assets[*]}"
{
  echo "### Published"
  for file in "$@"; do echo "- \`$(basename "$file")\` is now the download on the Releases page (\`${tag}\`)"; done
} >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
