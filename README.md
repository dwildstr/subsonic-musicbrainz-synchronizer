# subsonic-musicbrainz-synchronizer
This is a python script to synchronize MusicBrainz ratings with a Subsonic server in which records are identified with MusicBrainz IDs; it uses the py-sonic and musicbrainzngs libraries to communicate with the APIs of both servers.

At present only the "tracks" (`-t`) mode is implemented, although others will be added shortly.

Note that since MusicBrainz rate-limits API access to one per second, any synchronization which depends on querying MusicBrainz's own data for individual tracks will be very slow. In particular, any track-data synchronization other than a `--force-push`, or a `--push` in which very few of the tracks have ratings on the Subsonic side will take one second per track. If you have rated lots of tracks on a Subsonic server, `--force-push` is a great way to shove all of those ratings in large groups (10 at a time by default, although that's configurable) onto MusicBrainz.

# Bugs and Warnings
Use at your own risk. If you are extremely attached to your MusicBrainz or Subsonic metadata, understand that this script might well scribble all over them if it somehow gets bad information from one or the other service. It should err on the side of caution but I can make no promises.

If you use both the `--average` and `--force-pull` parameters, this script *will* overwrite your Subsonic data with Musicbrainz community-generated data. This is by design but is something you should only do if you really intend to do that.

If different tracks on a Subsonic server both have the same MusicBrainz recording ID (for instance, the same song on two different compilation albums), this script will attempt to synchronize both with the same MusicBrainz record, potentially leading to conflict.
