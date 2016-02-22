#!/usr/bin/env python
# encoding: UTF-8

"""
This file is part of commix (@commixproject) tool.
Copyright (c) 2014-2016 Anastasios Stasinopoulos (@ancst).
https://github.com/stasinopoulos/commix

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
 
For more see the file 'readme/COPYING' for copying permission.
"""

import re
import os
import sys
import random
import httplib
import urllib2

from socket import error as SocketError

# Disable SSL verification.
# For python versions 2.7.9 or above.
import ssl
try:
  _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
  # Legacy Python that doesn't verify HTTPS certificates by default
  pass
else:
  # Handle target environment that doesn't support HTTPS verification
  ssl._create_default_https_context = _create_unverified_https_context

from src.utils import menu
from src.utils import logs
from src.utils import update
from src.utils import version
from src.utils import install
from src.utils import settings
from src.utils import session_handler

from src.thirdparty.colorama import Fore, Back, Style, init

from src.core.requests import tor
from src.core.requests import proxy
from src.core.requests import headers
from src.core.requests import requests

from src.core.injections.controller import checks
from src.core.injections.controller import parser
from src.core.injections.controller import controller

# use Colorama to make Termcolor work on Windows too :)
if settings.IS_WINDOWS:
  init()

"""
The main function
"""
def main():
  try:
    # Check if defined "--version" option.
    if menu.options.version:
      version.show_version()
      sys.exit(0)

    # Checkall the banner
    menu.banner()
        
    # Check python version number.
    version.python_version()
            
    # Check if defined "--update" option.        
    if menu.options.update:
      update.updater()
      sys.exit(0)
        
    # Check if defined "--install" option.        
    if menu.options.install:
      install.installer()
      sys.exit(0)
    
    # Check arguments
    if len(sys.argv) == 1:
      menu.parser.print_help()
      print ""
      sys.exit(0)
    
    # Parse target / data from HTTP proxy logs (i.e Burp / WebScarab).
    if menu.options.logfile:
      parser.logfile_parser()
      
    # Modification on payload
    if not menu.options.shellshock:
      #settings.CURRENT_USER = "echo $(" + settings.CURRENT_USER + ")"
      settings.SYS_USERS  = "echo $(" + settings.SYS_USERS + ")"
      settings.SYS_PASSES  = "echo $(" + settings.SYS_PASSES + ")"

    # Check if defined character used for splitting parameter values.
    if menu.options.pdel:
     settings.PARAMETER_DELIMITER = menu.options.pdel

    # Check if defined character used for splitting cookie values.
    if menu.options.cdel:
     settings.COOKIE_DELIMITER = menu.options.cdel

    # Check if specified wrong injection technique
    if menu.options.tech and menu.options.tech not in settings.AVAILABLE_TECHNIQUES:
      found_tech = False
      # Convert injection technique(s) to lowercase
      menu.options.tech = menu.options.tech.lower()
      # Check if used the ',' separator
      if "," in menu.options.tech:
        split_techniques_names = menu.options.tech.split(",")
      else:
        split_techniques_names = menu.options.tech.split()
      if split_techniques_names:
        for i in range(0,len(split_techniques_names)):
          if len(menu.options.tech) <= 4:
            split_first_letter = list(menu.options.tech)
            for j in range(0,len(split_first_letter)):
              if split_first_letter[j] in settings.AVAILABLE_TECHNIQUES:
                found_tech = True
              else:  
                found_tech = False            
      if split_techniques_names[i].replace(' ', '') not in settings.AVAILABLE_TECHNIQUES and found_tech == False:
        error_msg = "You specified wrong value '" + split_techniques_names[i] + "' as injection technique. " \
                    "The value, must be a string composed by the letters (C)lassic, (E)val-based, " \
                    "(T)ime-based, (F)ile-based (with or without commas)."
        print Back.RED + settings.ERROR_SIGN + error_msg + Style.RESET_ALL
        sys.exit(0)

    # Cookie Injection
    if menu.options.cookie and settings.INJECT_TAG in menu.options.cookie:
      settings.COOKIE_INJECTION = True

    # User-Agent Injection
    if menu.options.agent and settings.INJECT_TAG in menu.options.agent:
      settings.USER_AGENT_INJECTION = True

    # Referer Injection
    if menu.options.referer and settings.INJECT_TAG in menu.options.referer:
      settings.REFERER_INJECTION = True

    # Check if specified wrong alternative shell
    if menu.options.alter_shell:
      if menu.options.alter_shell.lower() not in settings.AVAILABLE_SHELLS:
        print Back.RED + settings.ERROR_SIGN + "'" + menu.options.alter_shell + "' shell is not supported!" + Style.RESET_ALL
        sys.exit(0)

    # Check the file-destination
    if menu.options.file_write and not menu.options.file_dest or \
    menu.options.file_upload  and not menu.options.file_dest:
      print Back.RED + settings.ERROR_SIGN + "Host's absolute filepath to write and/or upload, must be specified (--file-dest)." + Style.RESET_ALL
      sys.exit(0)

    if menu.options.file_dest and menu.options.file_write == None and menu.options.file_upload == None :
       print Back.RED + settings.ERROR_SIGN + "You must enter the '--file-write' or '--file-upload' parameter." + Style.RESET_ALL
       sys.exit(0)

    # Check if defined "--file-upload" option.
    if menu.options.file_upload:
      # Check if not defined URL for upload.
      if not re.match(settings.VALID_URL_FORMAT, menu.options.file_upload):
        print Back.RED + settings.ERROR_SIGN + "The '" + menu.options.file_upload + "' is not a valid URL. " + Style.RESET_ALL
        sys.exit(0)
        
    # Check if defined "--random-agent" option.
    if menu.options.random_agent:
      menu.options.agent = random.choice(settings.USER_AGENT_LIST)
  
    # Check if defined "--url" option.
    if menu.options.url:

      url = menu.options.url
      
      # Check if http / https
      url = checks.check_http_s(url)

      if menu.options.output_dir:
        output_dir = menu.options.output_dir
      else:
        output_dir = settings.OUTPUT_DIR
      dir = os.path.dirname(output_dir)
      try:
        os.stat(output_dir)
      except:
        os.mkdir(output_dir)   

      # The logs filename construction.
      filename = logs.create_log_file(url, output_dir)
      try:
        
        # Check if defined POST data
        if menu.options.data:
          request = urllib2.Request(url, menu.options.data)
        else:
          request = urllib2.Request(url)
        headers.do_check(request)  
        
        # Check if defined any HTTP Proxy (--proxy option).
        if menu.options.proxy:
          proxy.do_check(url)
        
        # Check if defined Tor (--tor option).
        elif menu.options.tor:
          tor.do_check()
        sys.stdout.write(settings.INFO_SIGN + "Checking connection to the target URL... ")
        sys.stdout.flush()
        try:
          # Check if defined any HTTP Proxy (--proxy option).
          if menu.options.proxy:
            response = proxy.use_proxy(request)
          # Check if defined Tor (--tor option).  
          elif menu.options.tor:
            response = tor.use_tor(request)
          else:
            response = urllib2.urlopen(request)
        except:
          raise
        
        html_data = response.read()
        content = response.read()
        print "[ " + Fore.GREEN + "SUCCEED" + Style.RESET_ALL + " ]"
        try:
          if response.info()['server'] :
            server_banner = response.info()['server']
            found_os_server = False
            for i in range(0,len(settings.SERVER_OS_BANNERS)):
              if settings.SERVER_OS_BANNERS[i].lower() in server_banner.lower():
                found_os_server = True
                settings.TARGET_OS = settings.SERVER_OS_BANNERS[i].lower()
                if settings.TARGET_OS == "win" or settings.TARGET_OS == "microsoft" :
                  identified_os = "Windows"
                  settings.TARGET_OS = identified_os[:3].lower()
                  if menu.options.shellshock:
                    print Back.RED + settings.CRITICAL_SIGN + "The shellshock module is not available for " + identified_os + " targets." + Style.RESET_ALL
                    raise SystemExit()
                else:
                  identified_os = "Unix-like (" + settings.TARGET_OS + ")"
            
            found_server_banner = False
            for i in range(0,len(settings.SERVER_BANNERS)):
              if settings.SERVER_BANNERS[i].lower() in server_banner.lower():
                if menu.options.verbose:
                  print Style.BRIGHT + "(!) The server was identified as " + Style.UNDERLINE + server_banner + Style.RESET_ALL + "." + Style.RESET_ALL
                settings.SERVER_BANNER = server_banner
                found_server_banner = True
                # Set up default root paths
                if settings.SERVER_BANNERS[i].lower() == "apache":
                  if settings.TARGET_OS == "win":
                    settings.SRV_ROOT_DIR = "\\htdocs"
                  else:
                    settings.SRV_ROOT_DIR = "/var/www"
                if settings.SERVER_BANNERS[i].lower() == "nginx": 
                  settings.SRV_ROOT_DIR = "/usr/share/nginx"
                if settings.SERVER_BANNERS[i].lower() == "microsoft-iis":
                  settings.SRV_ROOT_DIR = "\\inetpub\\wwwroot"
                break

            if menu.options.is_admin or menu.options.is_root and not menu.options.current_user:
              menu.options.current_user = True

            # Check for wrong flags.
            if settings.TARGET_OS == "win":
              if menu.options.is_root :
                print Fore.YELLOW + settings.WARNING_SIGN + "Swithing '--is-root' to '--is-admin' because the target has been identified as windows." + Style.RESET_ALL 
              error_msg = settings.WARNING_SIGN + "The '--passwords' option, is not yet available for Windows targets."
              if menu.options.passwords:
                print Fore.YELLOW + settings.WARNING_SIGN + "The '--passwords' option, is not yet available for Windows targets." + Style.RESET_ALL   
              if menu.options.file_upload :
                print Fore.YELLOW + settings.WARNING_SIGN + "The '--file-upload' option, is not yet available for windows targets. Instead, use the '--file-write' option." + Style.RESET_ALL   
                sys.exit(0)
            else: 
              if menu.options.is_admin : 
                print Fore.YELLOW + settings.WARNING_SIGN + "Swithing the '--is-admin' to '--is-root' because the target has been identified as unix-like. " + Style.RESET_ALL   
            
            if found_os_server == False:
              # If "--shellshock" option is provided then,
              # by default is a Linux/Unix operating system.
              if menu.options.shellshock:
                pass 
              else:
                print Fore.YELLOW + settings.WARNING_SIGN + "Heuristics have failed to identify server's operating system." + Style.RESET_ALL 
                while True:
                  got_os = raw_input(settings.QUESTION_SIGN + "Do you recognise the server's operating system? [(W)indows/(U)nix/(q)uit] > ").lower()
                  if got_os.lower() in settings.CHOISE_OS :
                    if got_os.lower() == "w":
                      settings.TARGET_OS == "win"
                      break
                    elif got_os.lower() == "u":
                      break
                    elif got_os.lower() == "q":
                      raise SystemExit()
                  else:
                    if got_os == "":
                      got_os = "enter"
                    print Back.RED + settings.ERROR_SIGN + "'" + got_os + "' is not a valid answer." + Style.RESET_ALL + "\n"
                    pass
            if found_server_banner == False :
              print  Fore.YELLOW + settings.WARNING_SIGN + "The server which was identified as " + server_banner + " seems unknown." + Style.RESET_ALL
        except KeyError:
          pass

        # Charset detection [1].
        # [1] http://www.w3schools.com/html/html_charset.asp
        # Check if HTML4 format
        content = re.findall(r";charset=(.*)\"", html_data)
        if len(content) != 0 :
          charset = content
        else:
           # Check if HTML5 format
          charset = re.findall(r"charset=['\"](.*?)['\"]", html_data)
        if len(charset) != 0 :
          settings.CHARSET = charset[len(charset)-1]
          if settings.CHARSET.lower() not in settings.CHARSET_LIST:
            print  Fore.YELLOW + settings.WARNING_SIGN + "The indicated web-page charset "  + settings.CHARSET + " seems unknown." + Style.RESET_ALL
          else:
            if menu.options.verbose:
              print Style.BRIGHT + "(!) The indicated web-page charset appears to be "  + Style.UNDERLINE  + settings.CHARSET + Style.RESET_ALL + "." + Style.RESET_ALL

      except urllib2.HTTPError, e:
        print "[ " + Fore.RED + "FAILED" + Style.RESET_ALL + " ]"
        # Check the codes of responses
        if e.getcode() == 500:
          content = e.read()
          sys.exit(0)

        elif e.getcode() == 401:
          if menu.options.auth_type != "basic":
            print Back.RED + settings.ERROR_SIGN + "Only 'Basic' Access Authentication is supported." + Style.RESET_ALL
            sys.exit(0)
          else:
            print Back.RED + settings.ERROR_SIGN + "Authorization required!" + Style.RESET_ALL
            sys.exit(0)
          
        elif e.getcode() == 403:
          print Back.RED + settings.ERROR_SIGN + "You don't have permission to access this page." + Style.RESET_ALL
          sys.exit(0)
          
        elif e.getcode() == 404:
          print Back.RED + settings.ERROR_SIGN + "The host seems to be down!" + Style.RESET_ALL
          sys.exit(0)

        else:
          raise

      except urllib2.URLError, e:
        print "[ " + Fore.RED + "FAILED" + Style.RESET_ALL + " ]"
        print Back.RED + settings.ERROR_SIGN + "The host seems to be down!" + Style.RESET_ALL
        sys.exit(0)
        
      except httplib.BadStatusLine, e:
        print "[ " + Fore.RED + "FAILED" + Style.RESET_ALL + " ]"
        if len(e.line) > 2 :
          print e.line, e.message
        pass

    else:
      print Back.RED + settings.ERROR_SIGN + "You must specify the target URL." + Style.RESET_ALL
      sys.exit(0)

    # Launch injection and exploitation controller.
    controller.do_check(url, filename)

  except KeyboardInterrupt: 
    print "\n" + Back.RED + settings.ABORTION_SIGN + "Ctrl-C was pressed!" + Style.RESET_ALL
    if settings.SHOW_LOGS_MSG == True:
      logs.logs_notification(filename)
    print ""
    if menu.options.url:
      session_handler.clear(menu.options.url)
    sys.exit(0)

  except SystemExit: 
    if settings.SHOW_LOGS_MSG == True:
      logs.logs_notification(filename)
    print ""
    if menu.options.url:
      session_handler.clear(menu.options.url)
    sys.exit(0)
  
  # Accidental stop / restart of the target host server.
  except httplib.BadStatusLine, e:
    if e.line == "" or e.message == "":
      print "\n\n" + Back.RED + settings.CRITICAL_SIGN + "The target host is not responding." + \
            " Please ensure that is up and try again." + Style.RESET_ALL
      if settings.SHOW_LOGS_MSG == True:
        logs.logs_notification(filename)
      print ""
      sys.exit(0)      
    else: 
      print Back.RED + settings.ERROR_SIGN + e.line + e.message + Style.RESET_ALL + "\n"
    session_handler.clear(url)  
    sys.exit(0)

  # Connection reset by peer
  except SocketError, e:
    if menu.options.verbose:
      print ""
    print "\n" + Back.RED + settings.CRITICAL_SIGN + "The target host is not responding." + \
          " Please ensure that is up and try again." + Style.RESET_ALL 
    if settings.SHOW_LOGS_MSG == True:
      logs.logs_notification(filename)
    print ""
    session_handler.clear(url)
    sys.exit(0)
    
if __name__ == '__main__':
    main()
    
#eof