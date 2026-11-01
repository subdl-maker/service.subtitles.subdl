#!/bin/sh
# Prepares the container: a test CA for the mock API, Kodi's profile for user "viewer",
# the add-on copied from /addon, and two short test videos.
set -eu
OUT=/harness/out
mkdir -p "$OUT"
: > "$OUT/requests.jsonl"

# Test CA and a certificate for the two SubDL hostnames the mock answers for.
cd /tmp
openssl req -x509 -newkey rsa:2048 -nodes -days 2 -subj "/CN=SubDL e2e test CA" \
  -keyout ca.key -out ca.crt -addext "basicConstraints=critical,CA:true" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" -addext "subjectKeyIdentifier=hash" 2>/dev/null
openssl req -newkey rsa:2048 -nodes -subj "/CN=api.subdl.com" -keyout mock.key -out mock.csr 2>/dev/null
printf "subjectAltName=DNS:api.subdl.com,DNS:dl.subdl.com\nbasicConstraints=CA:false\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n" > ext.cnf
openssl x509 -req -in mock.csr -CA ca.crt -CAkey ca.key -CAcreateserial -days 2 -extfile ext.cnf -out mock.crt 2>/dev/null
cp ca.crt /usr/local/share/ca-certificates/subdl-e2e-test.crt
update-ca-certificates >/dev/null 2>&1

HOME_DIR=/home/viewer
KODI=$HOME_DIR/.kodi
mkdir -p "$KODI/addons" "$KODI/userdata/addon_data/service.subtitles.subdl" "$HOME_DIR/media"
rm -rf "$KODI/addons/service.subtitles.subdl"
cp -R /addon "$KODI/addons/service.subtitles.subdl"

cat > "$KODI/userdata/guisettings.xml" <<'XML'
<settings version="2">
    <setting id="services.webserver">true</setting>
    <setting id="services.webserverport">8080</setting>
    <setting id="services.webserverauthentication">true</setting>
    <setting id="services.webserverusername">kodi</setting>
    <setting id="services.webserverpassword">kodi</setting>
    <setting id="subtitles.languages">English,Persian</setting>
    <setting id="locale.subtitlelanguage">Persian</setting>
    <setting id="subtitles.movie">service.subtitles.subdl</setting>
    <setting id="subtitles.tv">service.subtitles.subdl</setting>
    <setting id="subtitles.storagemode">0</setting>
    <setting id="general.addonupdates">2</setting>
</settings>
XML
cat > "$KODI/userdata/advancedsettings.xml" <<'XML'
<advancedsettings version="1.0">
    <loglevel hide="false">1</loglevel>
</advancedsettings>
XML

for name in "The.Matrix.1999.1080p.BluRay.x264-GROUP" "Breaking.Bad.S01E05.720p.BluRay.x264-DEMAND"; do
  if [ ! -f "$HOME_DIR/media/$name.mkv" ]; then
    ffmpeg -loglevel error -f lavfi -i "testsrc=duration=300:size=640x360:rate=25" \
      -f lavfi -i "sine=frequency=440:duration=300" -c:v mpeg4 -q:v 8 -c:a mp2 \
      "$HOME_DIR/media/$name.mkv"
  fi
done
chown -R viewer:viewer "$HOME_DIR"
echo "setup done"
