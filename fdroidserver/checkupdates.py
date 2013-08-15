#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# checkupdates.py - part of the FDroid server tools
# Copyright (C) 2010-13, Ciaran Gultnieks, ciaran@ciarang.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import os
import re
import urllib2
import time
import subprocess
from optparse import OptionParser
import traceback
import HTMLParser
from distutils.version import LooseVersion
import common
from common import BuildException
from common import VCSException



# Check for a new version by looking at the tags in the source repo.
# Whether this can be used reliably or not depends on
# the development procedures used by the project's developers. Use it with
# caution, because it's inappropriate for many projects.
# Returns (None, "a message") if this didn't work, or (version, vercode) for
# the details of the current version.
def check_tags(app, sdk_path):

    try:

        if app['Repo Type'] == 'srclib':
            build_dir = os.path.join('build', 'srclib')
            repotype = common.getsrclibvcs(app['Repo'])
        else:
            build_dir = os.path.join('build/', app['id'])
            repotype = app['Repo Type']

        if repotype not in ('git', 'git-svn'):
            return (None, 'Tags update mode only works for git and git-svn repositories currently')

        # Set up vcs interface and make sure we have the latest code...
        vcs = common.getvcs(app['Repo Type'], app['Repo'], build_dir, sdk_path)

        if app['Repo Type'] == 'srclib':
            build_dir = os.path.join(build_dir, app['Repo'])

        vcs.gotorevision(None)

        flavour = None
        if len(app['builds']) > 0:
            if 'subdir' in app['builds'][-1]:
                build_dir = os.path.join(build_dir, app['builds'][-1]['subdir'])
            if 'gradle' in app['builds'][-1]:
                flavour = app['builds'][-1]['gradle']

        hver = None
        hcode = "0"

        for tag in vcs.gettags():
            vcs.gotorevision(tag)

            # Only process tags where the manifest exists...
            paths = common.manifest_paths(build_dir, flavour)
            version, vercode, package = common.parse_androidmanifests(paths)
            if package and package == app['id'] and version and vercode:
                print "Manifest exists. Found version %s" % version
                if int(vercode) > int(hcode):
                    hcode = str(int(vercode))
                    hver = version

        if hver:
            return (hver, hcode)
        return (None, "Couldn't find any version information")

    except BuildException as be:
        msg = "Could not scan app %s due to BuildException: %s" % (app['id'], be)
        return (None, msg)
    except VCSException as vcse:
        msg = "VCS error while scanning app %s: %s" % (app['id'], vcse)
        return (None, msg)
    except Exception:
        msg = "Could not scan app %s due to unknown error: %s" % (app['id'], traceback.format_exc())
        return (None, msg)

# Check for a new version by looking at the AndroidManifest.xml at the HEAD
# of the source repo. Whether this can be used reliably or not depends on
# the development procedures used by the project's developers. Use it with
# caution, because it's inappropriate for many projects.
# Returns (None, "a message") if this didn't work, or (version, vercode) for
# the details of the current version.
def check_repomanifest(app, sdk_path, branch=None):

    try:

        if app['Repo Type'] == 'srclib':
            build_dir = os.path.join('build', 'srclib')
            repotype = common.getsrclibvcs(app['Repo'])
        else:
            build_dir = os.path.join('build/', app['id'])
            repotype = app['Repo Type']

        # Set up vcs interface and make sure we have the latest code...
        vcs = common.getvcs(app['Repo Type'], app['Repo'], build_dir, sdk_path)
        if app['Repo Type'] == 'srclib':
            build_dir = os.path.join(build_dir, app['Repo'])

        if vcs.repotype() == 'git':
            if branch:
                vcs.gotorevision('origin/'+branch)
            else:
                vcs.gotorevision('origin/master')
                pass
        elif vcs.repotype() == 'git-svn':
            if branch:
                vcs.gotorevision(branch)
            else:
                vcs.gotorevision(None)
        elif vcs.repotype() == 'svn':
            vcs.gotorevision(None)
        elif vcs.repotype() == 'hg':
            if branch:
                vcs.gotorevision(branch)
            else:
                vcs.gotorevision('default')
        elif vcs.repotype() == 'bzr':
            vcs.gotorevision(None)

        flavour = None

        if len(app['builds']) > 0:
            if 'subdir' in app['builds'][-1]:
                build_dir = os.path.join(build_dir, app['builds'][-1]['subdir'])
            if 'gradle' in app['builds'][-1]:
                flavour = app['builds'][-1]['gradle']

        if not os.path.isdir(build_dir):
            return (None, "Subdir '" + app['builds'][-1]['subdir'] + "'is not a valid directory")

        paths = common.manifest_paths(build_dir, flavour)

        version, vercode, package = common.parse_androidmanifests(paths)
        if not package:
            return (None, "Couldn't find package ID")
        if package != app['id']:
            return (None, "Package ID mismatch")
        if not version:
            return (None,"Couldn't find latest version name")
        if not vercode:
            return (None,"Couldn't find latest version code")

        return (version, str(int(vercode)))

    except BuildException as be:
        msg = "Could not scan app %s due to BuildException: %s" % (app['id'], be)
        return (None, msg)
    except VCSException as vcse:
        msg = "VCS error while scanning app %s: %s" % (app['id'], vcse)
        return (None, msg)
    except Exception:
        msg = "Could not scan app %s due to unknown error: %s" % (app['id'], traceback.format_exc())
        return (None, msg)


# Check for a new version by looking at the Google Play Store.
# Returns (None, "a message") if this didn't work, or (version, None) for
# the details of the current version.
def check_gplay(app):
    time.sleep(15)
    url = 'https://play.google.com/store/apps/details?id=' + app['id']
    headers = {'User-Agent' : 'Mozilla/5.0 (X11; Linux i686; rv:18.0) Gecko/20100101 Firefox/18.0'}
    req = urllib2.Request(url, None, headers)
    try:
        resp = urllib2.urlopen(req, None, 20)
        page = resp.read()
    except urllib2.HTTPError, e:
        return (None, str(e.code))
    except Exception, e:
        return (None, 'Failed:' + str(e))

    version = None

    m = re.search('itemprop="softwareVersion">[ ]*([^<]+)[ ]*</div>', page)
    if m:
        html_parser = HTMLParser.HTMLParser()
        version = html_parser.unescape(m.group(1))

    if version == 'Varies with device':
        return (None, 'Device-variable version, cannot use this method')

    if not version:
        return (None, "Couldn't find version")
    return (version.strip(), None)


def main():

    #Read configuration...
    globals()['gradle'] = "gradle"
    execfile('config.py', globals())

    # Parse command line...
    parser = OptionParser()
    parser.add_option("-v", "--verbose", action="store_true", default=False,
                      help="Spew out even more information than normal")
    parser.add_option("-p", "--package", default=None,
                      help="Check only the specified package")
    parser.add_option("--auto", action="store_true", default=False,
                      help="Process auto-updates")
    parser.add_option("--autoonly", action="store_true", default=False,
                      help="Only process apps with auto-updates")
    parser.add_option("--commit", action="store_true", default=False,
                      help="Commit changes")
    parser.add_option("--gplay", action="store_true", default=False,
                      help="Only print differences with the Play Store")
    (options, args) = parser.parse_args()

    # Get all apps...
    apps = common.read_metadata(options.verbose)

    # Filter apps according to command-line options
    if options.package:
        apps = [app for app in apps if app['id'] == options.package]
        if len(apps) == 0:
            print "No such package"
            sys.exit(1)

    if options.gplay:
        for app in apps:
            version, reason = check_gplay(app)
            if version is None and options.verbose:
                if reason == '404':
                    print "%s (%s) is not in the Play Store" % (app['Auto Name'], app['id'])
                else:
                    print "%s (%s) encountered a problem: %s" % (app['Auto Name'], app['id'], reason)
            if version is not None:
                stored = app['Current Version']
                if LooseVersion(stored) < LooseVersion(version):
                    print "%s (%s) has version %s on the Play Store, which is bigger than %s" % (
                            app['Auto Name'], app['id'], version, stored)
                elif options.verbose:
                    print "%s (%s) has the same version %s on the Play Store" % (
                            app['Auto Name'], app['id'], version)
        return


    for app in apps:

        process = True

        if options.autoonly and app['Auto Update Mode'] == 'None':
            process = False

        if process:

            print "Processing " + app['id'] + '...'

            writeit = False
            logmsg = None

            mode = app['Update Check Mode']
            if mode == 'Tags':
                (version, vercode) = check_tags(app, sdk_path)
            elif mode == 'RepoManifest':
                (version, vercode) = check_repomanifest(app, sdk_path)
            elif mode.startswith('RepoManifest/'):
                (version, vercode) = check_repomanifest(app, sdk_path, mode[13:])
            elif mode == 'Static':
                version = None
                vercode = 'Checking disabled'
            elif mode == 'None':
                version = None
                vercode = 'Checking disabled'
            else:
                version = None
                vercode = 'Invalid update check method'

            if not version:
                print "..." + vercode
            elif vercode == app['Current Version Code'] and version == app['Current Version']:
                print "...up to date"
            else:
                print '...updating to version:' + version + ' vercode:' + vercode
                app['Current Version'] = version
                app['Current Version Code'] = str(int(vercode))
                writeit = True
                logmsg = "Update current version of " + app['id'] + " to " + version

            # Do the Auto Name thing as well as finding the CV real name
            if len(app["Repo Type"]) > 0:

                try:

                    if app['Repo Type'] == 'srclib':
                        app_dir = os.path.join('build', 'srclib', app['Repo'])
                    else:
                        app_dir = os.path.join('build/', app['id'])

                    vcs = common.getvcs(app["Repo Type"], app["Repo"], app_dir, sdk_path)
                    vcs.gotorevision(None)

                    flavour = None
                    if len(app['builds']) > 0:
                        if 'subdir' in app['builds'][-1]:
                            app_dir = os.path.join(app_dir, app['builds'][-1]['subdir'])
                        if 'gradle' in app['builds'][-1]:
                            flavour = app['builds'][-1]['gradle']

                    new_name = common.fetch_real_name(app_dir, flavour)
                    if new_name != app['Auto Name']:
                        app['Auto Name'] = new_name
                        writeit = True

                    if app['Current Version'].startswith('@string/'):
                        cv = common.version_name(app['Current Version'], app_dir, flavour)
                        if app['Current Version'] != cv:
                            app['Current Version'] = cv
                            writeit = True
                except Exception:
                    msg = "Auto Name or Current Version failed for %s due to exception: %s" % (app['id'], traceback.format_exc())

            if options.auto:
                mode = app['Auto Update Mode']
                if mode == 'None':
                    pass
                elif mode.startswith('Version '):
                    pattern = mode[8:]
                    if pattern.startswith('+'):
                        o = pattern.find(' ')
                        suffix = pattern[1:o]
                        pattern = pattern[o + 1:]
                    else:
                        suffix = ''
                    gotcur = False
                    latest = None
                    for build in app['builds']:
                        if build['vercode'] == app['Current Version Code']:
                            gotcur = True
                        if not latest or int(build['vercode']) > int(latest['vercode']):
                            latest = build
                    if not gotcur:
                        newbuild = latest.copy()
                        del newbuild['origlines']
                        newbuild['vercode'] = app['Current Version Code']
                        newbuild['version'] = app['Current Version'] + suffix
                        print "...auto-generating build for " + newbuild['version']
                        commit = pattern.replace('%v', newbuild['version'])
                        commit = commit.replace('%c', newbuild['vercode'])
                        newbuild['commit'] = commit
                        app['builds'].append(newbuild)
                        writeit = True
                        logmsg = "Update " + app['id'] + " to " + newbuild['version']
                else:
                    print 'Invalid auto update mode'

            if writeit:
                metafile = os.path.join('metadata', app['id'] + '.txt')
                common.write_metadata(metafile, app)
                if options.commit and logmsg:
                    if subprocess.call("git add " + metafile, shell=True) != 0:
                        print "Git add failed"
                        sys.exit(1)
                    if subprocess.call("git commit -m '" + logmsg.replace("'", "\\'") +  "'", shell=True) != 0:
                        print "Git commit failed"
                        sys.exit(1)

    print "Finished."

if __name__ == "__main__":
    main()

