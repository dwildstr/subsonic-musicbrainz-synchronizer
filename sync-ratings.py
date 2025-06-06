#!/usr/bin/env python

import libsonic
import musicbrainzngs as mb
import argparse,math

parser = argparse.ArgumentParser(description='Synchronize MusicBrainz and Subsonic ratings')

parser.add_argument('-v', '--verbose',help='Increase verbosity',action='count',default=0)

parser.add_argument('-d', '--dry-run',help='Report intended actions but do not actually synchronize ratings',action='store_true')

parser.add_argument('-n', '--search-size',help='Number of records to pull from Subsonic server with each query',metavar='#',type=int,default=50)

parser.add_argument('-N', '--submission-queue-size',help='Maximum number of updates to push at once to MusicBrainz',metavar='#',type=int,default=10)


loginconfig=parser.add_argument_group('Login configuration','Necessary configuration for remote services')
loginconfig.add_argument('-S', '--server',help='URL for subsonic server (including protocol, without port)',required=True)
loginconfig.add_argument('-P', '--port',help='port for subsonic server',required=True,type=int)
loginconfig.add_argument('-u', '--ssusername',help='Username for Subsonic server',metavar='NAME',required=True)
loginconfig.add_argument('-w', '--sspassword',help='Password for Subsonic server',metavar='PWORD',required=True)
loginconfig.add_argument('-U', '--mbusername',help='Username for MusicBrainz',metavar='NAME',required=True)
loginconfig.add_argument('-W', '--mbpassword',help='Password for MusicBrainz',metavar='PWORD',required=True)

recordtypes=parser.add_argument_group("Record types","Which records to synchronize")

recordtypes.add_argument('-a', '--albums',help='Synchronize album ratings',action='store_true')
recordtypes.add_argument('-A', '--artists',help='Synchronize artist ratings',action='store_true')
recordtypes.add_argument('-t', '--tracks',help='Synchronize track ratings',action='store_true')


syncmodeaux=parser.add_argument_group("Synchronization mode","Direction to synchronize data")
syncmode=syncmodeaux.add_mutually_exclusive_group()

syncmode.add_argument('--sync',help='Synchronize ratings in both directions (default)',action='store_true')
syncmode.add_argument('--push',help='Only push Subsonic ratings to Musicbrainz',action='store_true')
syncmode.add_argument('--pull',help='Only pull Subsonic ratings from Musicbrainz',action='store_true')
syncmode.add_argument('--average',help='Only pull average ratings (rounding up)',action='store_true')
syncmodeaux.add_argument('--average-minimum',help='Only pull average ratings with at least N ratings',metavar='N',type=int,default=1)

conflictmode=parser.add_argument_group("Conflict resolution mode","How to resolve conflicting data").add_mutually_exclusive_group()

conflictmode.add_argument('--prompt',help='Prompt user for resolution of conflicts (default)',action='store_true')
conflictmode.add_argument('--batch',help='Ignore synchronization conflicts without resolving',action='store_true')
conflictmode.add_argument('--force-push',help='Resolve synchronization conflicts in favor of Subsonic',action='store_true')
conflictmode.add_argument('--force-pull',help='Resolve synchronization conflicts in favor of MusicBrainz',action='store_true')

args=parser.parse_args()

sonic=libsonic.Connection(args.server,args.ssusername,args.sspassword,args.port)
mb.set_useragent("Subsonic ratings synchronizer", "0.1", "djw3141592@gmail.com")
mb.auth(args.mbusername,args.mbpassword)


mb_update_queue_size=0
mb_update_queue={}

def ssPrintable(ssData):
    output=""
    if "artist" in ssData:
        output  = output + ssData["artist"]
    if "album" in ssData:
        output  = output + " - " + ssData["album"]
    if "title" in ssData:
        output  = output + " - " + ssData["title"]
    return output

def pushSSRating(id,rating):
    if not args.dry_run:
        sonic.setRating(id,rating)

def submitMBUpdates():
    global mb_update_queue_size,mb_update_queue
    if args.verbose>2:
        print("Submitting user ratings to MusicBrainz of",mb_update_queue)
    mb.submit_ratings(**mb_update_queue)
    mb_update_queue={}
    mb_update_queue_size=0
    

def pushMBRating(id,rating,type):
    global mb_update_queue_size,mb_update_queue

    if not args.dry_run:
        if (type+"_ratings") not in mb_update_queue:
            mb_update_queue[type+"_ratings"]={}
        # Note: MusicBrainz uses 0-100, not 0-5.
        mb_update_queue[type+"_ratings"][id]=rating*20
        mb_update_queue_size=mb_update_queue_size+1
        if mb_update_queue_size>=args.submission_queue_size:
            submitMBUpdates()

searchOffset=0
rated=0
unrated=0
while args.tracks:
    result=sonic.search2("",artistCount=0,albumCount=0,songCount=args.search_size,songOffset=searchOffset)["searchResult2"]
    if not result:
        # End of the search
        break 
    for ssData in result["song"]:
        if args.verbose>2:
            print("Analyzing record for",ssPrintable(ssData))
        if not "musicBrainzId" in ssData:
            # No musicBrainz ID, can't synchronize.
            if args.verbose>0:
                print("No musicBrainz ID for",ssPrintable(ssData))
                continue
        if args.push and (not "userRating" in ssData):
            # No rating to push; stop processing
            if args.verbose>1:
                print("No Subsonic rating for",ssPrintable(ssData)," -- nothing to push")
                continue
        mbRating=0
        if not args.force_push:
            # For a forced push, assume an empty MB rating instead of
            # actually wasting an API request.
            if args.average:
                mbData=mb.get_recording_by_id(ssData["musicBrainzId"],includes=["ratings"])['recording']
                if "rating" in mbData and (int(mbData["rating"]["votes-count"]) >= args.average_minimum):
                    mbRating=math.ceil(float(mbData["rating"]["rating"]))
            else:
                mbData=mb.get_recording_by_id(ssData["musicBrainzId"],includes=["user-ratings"])['recording']
                if "user-rating" in mbData:
                    mbRating=int(mbData["user-rating"])

        ssRating=0
        if (not args.force_pull) and ("userRating" in ssData):
            # For a forced pull, we zero out the SS rating
            ssRating=ssData["userRating"]
        if args.verbose>2:
            print("Analysis of ",ssPrintable(ssData)," has MB rating",mbRating," and SS rating",ssRating)
        if (ssRating==mbRating):
            # No difference; do  nothing
            if args.verbose>1:
                print("Identical ratings for",ssPrintable(ssData))
        elif (ssRating==0):
            if args.push:
                # I'm pretty sure this line should never actually be
                # executed, because we had the push failure earlier?
                if args.verbose>0:
                    print("Ignoring MB rating of", mbRating ,"for",ssPrintable(ssData)," (not pulling)")
            else:
                if args.verbose>0:
                    print("Updating rating of", mbRating ," for ",ssPrintable(ssData)," on Subsonic")
                pushSSRating(ssData["id"],mbRating)
        elif (mbRating==0):
            if args.pull:
                if args.verbose>0:
                    print("Ignoring SS rating of", mbRating ,"for",ssPrintable(ssData)," (not pushing)")
            else:
                if args.verbose>0:
                    print("Updating rating of", ssRating ,"for",ssPrintable(ssData)," on MusicBrainz")
                pushMBRating(ssData["musicBrainzId"],ssRating,"recording")
        else:
            # Conflicting data; this should never arise in a force
            # situation (since forced-push and forced-pull use
            # zero-rating shortcuts), and as a result we either have a
            # batch mode (when we do no resolution) or a user prompt.
            print("Conflicting ratings for ",ssPrintable(ssData)," between SS rating of ",ssRating," and MB rating of ",mbRating)
            if not args.batch:
                if args.push:
                    selectionPrompt="Use [S]ubsonic rating or [I]gnore? "
                elif args.pull:
                    selectionPrompt="Use [M]usicBrainz rating or [I]gnore? "
                else:
                    selectionPrompt="Use [S]ubsonic rating, [M]usicBrainz rating, or [I]gnore?"
                while True:
                    choice=input(selectionPrompt)
                    if (choice=="S" or choice=="s") and not args.pull:
                        pushMBRating(ssData["musicBrainzId"],mbRating,"recording")
                        break
                    if (choice=="M" or choice=="m") and not args.push:
                        pushSSRating(ssData["id"],mbRating)
                        break
                    if choice=="I" or choice=="i":
                        break
    searchOffset = searchOffset+args.search_size
# Flush the leftover updates
submitMBUpdates()
