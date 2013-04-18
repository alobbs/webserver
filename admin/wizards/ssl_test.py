# -*- coding: utf-8 -*-
#
# Cherokee-admin's Common Static wizard
#
# Authors:
#      Alvaro Lopez Ortega <alvaro@alobbs.com>
#
# Copyright (C) 2001-2013 Alvaro Lopez Ortega
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of version 2 of the GNU General Public
# License as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.
#

import re
import CTK
import Certs
import Wizard
import validations

from util import *
from configured import *

NOTE_WELCOME_H1 = N_("Welcome to the SSL/TLS Testing wizard")
NOTE_WELCOME_P1 = N_("This wizard adds SSL/TLS support to the virtual server for testing purposes.")
NOTE_WELCOME_P2 = N_("It will auto-configure the server to handle https requests by using a self-signed certificate. (Remember: This shouldn't be used on production!)")

NOTE_CERT                = N_("Full path to the PEM-encoded Certificate file for the server.")
NOTE_CERT_KEY            = N_("Full path to the PEM-encoded Private Key file for the server.")
NOTE_GEN_SELFSIGNED_CERT = N_("Generate and use a self-signed certificate.")

PREFIX    = 'tmp!wizard!ssl_test'
URL_APPLY = r'/wizard/vserver/ssl_test/apply'

VALS = [
    ('%s!cert'%(PREFIX),     validations.is_local_file_exists),
    ('%s!cert_key'%(PREFIX), validations.is_local_file_exists)
]

class Commit:
    def Commit_Rule (self):
        vsrv_num  = CTK.cfg.get_val ('%s!vsrv_num'%(PREFIX))
        auto_cert = int (CTK.cfg.get_val ('%s!gen_autosigned_cert'%(PREFIX), "1"))

        if not auto_cert:
            cert_fp     = CTK.cfg.get_val ('%s!cert'%(PREFIX))
            cert_key_fp = CTK.cfg.get_val ('%s!cert_key'%(PREFIX))
        else:
            # Certs dir
            cert_dir = os.path.join (CHEROKEE_VAR_LIB, "certs")
            if not os.path.exists (cert_dir):
                try:
                    os.makedirs (cert_dir)
                except e:
                    return {'ret': 'error', 'errors': {'%s!cert_key'%(PREFIX): str(e)}}

            # Cert files
            cert_fp     = os.path.join (cert_dir, "autogenerated.crt")
            cert_key_fp = os.path.join (cert_dir, "autogenerated.key")

            if not os.path.exists (cert_fp) or \
               not os.path.exists (cert_key_fp):
                error = Certs.create_selfsigned_cert (cert_dir, "autogenerated", "*")
                if error:
                    return {'ret': 'error', 'errors': {'%s!cert_key'%(PREFIX): error}}

        #
        # Tweak the configuration
        #

        # General SSL support
        if not CTK.cfg.get_val('server!tls'):
            CTK.cfg['server!tls'] = 'libssl'

        # HTTPS Port
        k_max       = 0
        https_found = False

        for k in CTK.cfg.keys('server!bind'):
            k_max = max (k_max, int(k))
            if CTK.cfg.get_val ('server!bind!%s!port'%(k)) == '443':
                https_found = True
                if CTK.cfg.get_val ('server!bind!%s!tls'%(k)) != '1':
                    CTK.cfg['server!bind!%s!tls'%(k)] = '1'

        if not https_found:
            CTK.cfg['server!bind!%s!port'%(k_max + 1)] = '443'
            CTK.cfg['server!bind!%s!tls' %(k_max + 1)] = '1'

        # VServer support
        CTK.cfg['vserver!%s!ssl_certificate_file'    %(vsrv_num)] = cert_fp
        CTK.cfg['vserver!%s!ssl_certificate_key_file'%(vsrv_num)] = cert_key_fp

        # Default VServer support is mandatory
        vs = [int(x) for x in CTK.cfg.keys('vserver')]
        vs.sort()
        default_pre = "vserver!%s" %(vs[0])

        if not CTK.cfg.get_val('%s!ssl_certificate_file'%(default_pre)):
            CTK.cfg['%s!ssl_certificate_file'    %(default_pre)] = cert_fp
            CTK.cfg['%s!ssl_certificate_key_file'%(default_pre)] = cert_key_fp

        return CTK.cfg_reply_ajax_ok()

    def __call__ (self):
        if CTK.post.pop('final'):
            CTK.cfg_apply_post()
            return self.Commit_Rule()

        return CTK.cfg_apply_post()


class Create:
    def __call__ (self):
        cont = CTK.Container()
        check_new_cert = CTK.CheckCfgText ('%s!gen_autosigned_cert'%(PREFIX), True, _("New self-signed cert."))

        table = CTK.PropsTable()
        table.Add (_('Auto-generate Certificate'), check_new_cert, _(NOTE_GEN_SELFSIGNED_CERT))

        submit = CTK.Submitter (URL_APPLY)
        submit += table

        # Certs details
        table = CTK.PropsTable()
        table.Add (_('Certificate'),     CTK.TextCfg ('%s!cert'    %(PREFIX), False, {'class':'noauto'}), _(NOTE_CERT))
        table.Add (_('Certificate Key'), CTK.TextCfg ('%s!cert_key'%(PREFIX), False, {'class':'noauto'}), _(NOTE_CERT_KEY))

        cert_details = CTK.Box ({'style': 'display:none;'})
        cert_details += table

        submit_certs = CTK.Submitter (URL_APPLY)
        submit_certs += cert_details

        # Events
        check_new_cert.bind ('change',
                             "if ($(this).find(':checked').size() <= 0) {%s} else {%s}"
                             %(cert_details.JS_to_show(), cert_details.JS_to_hide()))

        # Layout
        cont += CTK.RawHTML ("<h2>%s</h2>" %(_("Certificate file")))
        cont += submit
        cont += submit_certs

        # Global Submit
        submit = CTK.Submitter (URL_APPLY)
        submit += CTK.Hidden('final', '1')
        cont += submit

        cont += CTK.DruidButtonsPanel_PrevCreate_Auto()
        return cont.Render().toStr()


class Welcome:
    def __call__ (self):
        cont = CTK.Container()
        cont += CTK.RawHTML ('<h2>%s</h2>' %(_(NOTE_WELCOME_H1)))
        cont += Wizard.Icon ('ssl_test', {'class': 'wizard-descr'})

        box = CTK.Box ({'class': 'wizard-welcome'})
        box += CTK.RawHTML ('<p>%s</p>' %(_(NOTE_WELCOME_P1)))
        box += CTK.RawHTML ('<p>%s</p>' %(_(NOTE_WELCOME_P2)))
        cont += box

        # Send the VServer num
        tmp = re.findall (r'^/wizard/vserver/(\d+)/', CTK.request.url)
        submit = CTK.Submitter (URL_APPLY)
        submit += CTK.Hidden('%s!vsrv_num'%(PREFIX), tmp[0])
        cont += submit

        cont += CTK.DruidButtonsPanel_Next_Auto()
        return cont.Render().toStr()


# Rule
CTK.publish ('^/wizard/vserver/(\d+)/ssl_test$',  Welcome)
CTK.publish ('^/wizard/vserver/(\d+)/ssl_test/2', Create)
CTK.publish (r'^%s'%(URL_APPLY), Commit, method="POST", validation=VALS)
