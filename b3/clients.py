#
# BigBrotherBot(B3) (www.bigbrotherbot.com)
# Copyright (C) 2005 Michael "ThorN" Thornton
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
# $Id: clients.py 102 2006-04-14 06:46:03Z thorn $
#
# CHANGELOG
#    5/6/2008 - 1.2.5 - xlr8or
#    Client object now saves the current IP in auth function
#    10/29/2005 - 1.2.0 - ThorN
#    Removed direct references to PunkBuster. Authorization is now proxied
#     through the console.
#    7/23/2005 - 1.1.0 - ThorN
#    Added data field to Penalty
#    Added data parameter to Client.warn()
#    Added data parameter to Client.tempban()

__author__  = 'ThorN'
__version__ = '1.2.5'

import b3, string, re, time, functions, threading, weakref, traceback, sys

class ClientVar(object):
    value = None

    def __init__(self, value):
        self.value = value

    def toInt(self):
        if self.value == None:
            return 0

        return int(self.value)

    def toString(self):
        if self.value == None:
            return ''

        return str(self.value)

    def items(self):
        if self.value == None:
            return ()

        return self.value.items()

    def length(self):
        if self.value == None:
            return 0

        return len(self.value)

#-----------------------------------------------------------------------------------------------------------------------
class Client(object):
    # fields in storage
    guid = ''
    pbid = ''
    name = ''
    ip   = ''
    greeting = ''
    autoLogin = 1
    maskLevel = 0
    groupBits = 0

    # fields on object
    console = None
    exactName = None
    team = -1
    maxGroup = None
    authed = False
    hide = False

    state = None
    authorizing = False
    connected = True

    _pluginData = None
    _timeAdd = 0
    _timeEdit = 0
    _tempLevel = None
    _cid = None
    _data = None

    def __init__(self, **kwargs):
        self._pluginData = {}
        self.state = b3.STATE_UNKNOWN
        self._data = {}        

        for k, v in kwargs.iteritems():
            setattr(self, k, v)

    def isvar(self, plugin, key):
        try:
            d = self._pluginData[id(plugin)][key]
            return True
        except:
            return False

    def setvar(self, plugin, key, value=None):
        try:
            self._pluginData[id(plugin)]
        except:
            self._pluginData[id(plugin)] = {}

        try:
            self._pluginData[id(plugin)][key].value = value
        except:
            self._pluginData[id(plugin)][key] = ClientVar(value)

        return self._pluginData[id(plugin)][key]

    def var(self, plugin, key, default=None):
        try:
            return self._pluginData[id(plugin)][key]
        except:
            return self.setvar(plugin, key, default)

    def varlist(self, plugin, key, default=None):
        if not default:
            default = []

        return self.var(plugin, key, default)

    def vardict(self, plugin, key, default=None):
        if not default:
            default = {}

        return self.var(plugin, key, default)

    def delvar(self, plugin, key):
        try:
            del self._pluginData[id(plugin)][key]
        except:
            pass

    def getBans(self):
        return self.console.storage.getClientPenalties(self, type=('Ban', 'TempBan'))

    bans = property(getBans)

    def getWarnings(self):
        return self.console.storage.getClientPenalties(self, type='Warning')

    warnings = property(getWarnings)

    _groups = None
    def getGroups(self):
        if not self._groups:
            self._groups = []
            groups = self.console.storage.getGroups()

            for g in groups:
                if g.id & self._groupBits:
                    self._groups.append(g)

        return self._groups

    groups = property(getGroups)

    def getAliases(self):
        return self.console.storage.getClientAliases(self)

    aliases = property(getAliases)

    def getattr(self, name, default=None):
        return getattr(self, name, default)

    #------------------------
    _pbid = ''
    def _set_pbid(self, pbid):
        if self.getattr('_pbid') and self._pbid != pbid:
            self.console.error('Client has pbid but its not the same %s <> %s', self._pbid, pbid)

        self._pbid = pbid

    def _get_pbid(self):
        return self._pbid

    pbid = property(_get_pbid, _set_pbid)

    #------------------------
    _guid = ''
    def _set_guid(self, guid):
        if guid and len(guid) > 2:
            if self._guid and self._guid != guid:
                self.console.error('Client has guid but its not the same %s <> %s', self._guid, guid)
                self.authed = False
            elif not self._guid:
                self._guid = guid
        else:
            self.authed = False
            self._guid = ''

    def _get_guid(self):
        return self._guid

    guid = property(_get_guid, _set_guid)

    #------------------------
    _groupBits = 0
    def _set_groupBits(self, bits):
        self._groupBits = int(bits)
        self.refreshLevel()

    def _get_groupBits(self):
        return self._groupBits

    groupBits = property(_get_groupBits, _set_groupBits)

    def addGroup(self, group):
        self.groupBits = self.groupBits | group.id

    def setGroup(self, group):
        self.groupBits = group.id

    def remGroup(self, group):
        self.groupBits = self.groupBits ^ group.id

    def inGroup(self, group):
        return self.groupBits & group.id

    #------------------------
    _id = 0
    def _set_id(self, v):
        if not v:
            self._id = 0
        else:
            self._id = int(v)

    def _get_id(self):
        return self._id

    id = property(_get_id, _set_id)

    #------------------------
    _connections = 0
    def _set_connections(self, v):
        self._connections = int(v)

    def _get_connections(self):
        return self._connections

    connections = property(_get_connections, _set_connections)

    #------------------------
    _maskLevel = 0
    def _set_maskLevel(self, v):
        self._maskLevel = int(v)

    def _get_maskLevel(self):
        return self._maskLevel

    maskLevel = property(_get_maskLevel, _set_maskLevel)

    #------------------------
    _maskGroup = None
    def _set_maskGroup(self, g):
        self.maskLevel = g.id
        self._maskGroup = None

    def _get_maskGroup(self):
        if not self.maskLevel:
            return None
        elif not self._maskGroup:
            groups = self.console.storage.getGroups()

            for g in groups:
                if g.id & self.maskLevel:
                    self._maskGroup = g
                    break

        return self._maskGroup

    maskGroup = property(_get_maskGroup, _set_maskGroup)

    def _get_maskedGroup(self):
        group = self.maskGroup
        if group:
            return group
        else:
            return self.maxGroup

    maskedGroup = property(_get_maskedGroup)

    def _get_maskedLevel(self):
        group = self.maskedGroup
        if group:
            return group.level
        else:
            return 0

    maskedLevel = property(_get_maskedLevel)

    #------------------------
    _ip = ''
    def _set_ip(self, ip):
        if ':' in ip:
            self._ip = ip[0:ip.find(':')]
        else:
            self._ip = ip

        self._ip = ip

    def _get_ip(self):
        return self._ip

    ip = property(_get_ip, _set_ip)

    #------------------------
    def _set_timeAdd(self, time):
        self._timeAdd = int(time)

    def _get_timeAdd(self):
        return self._timeAdd

    timeAdd = property(_get_timeAdd, _set_timeAdd)

    #------------------------
    def _set_cid(self, cid):
        self.console.verbose('%s cid changed from %s to %s', self.id, self._cid, cid)
        self._cid = str(cid)

    def _get_cid(self):
        return self._cid

    cid = property(_get_cid, _set_cid)

    #------------------------
    def _set_data(self, data):
        for k, v in data.iteritems():
            self._data[k] = v

    def _get_data(self):
        return self._data

    data = property(_get_data, _set_data)

    #------------------------
    def _set_timeEdit(self, time):
        self._timeEdit = int(time)

    def _get_timeEdit(self):
        return self._timeEdit

    timeEdit = property(_get_timeEdit, _set_timeEdit)

    #------------------------
    _team = -1
    def _set_team(self, team):
        if self._team != team:
            self._team = team
            if self.console:
                self.console.queueEvent(b3.events.Event(b3.events.EVT_CLIENT_TEAM_CHANGE, self.team, self))

    def _get_team(self):
        return self._team

    team = property(_get_team, _set_team)

    #------------------------
    _name = ''
    _exactName = ''

    def _set_name(self, name):
        ename = name
        if self.console:
            name = self.console.stripColors(ename)

        if self._exactName != ename:
            if self._name and self._name != name:
                self.makeAlias(self._name)

            self._name = name
            self._exactName = ename + '^7'

            if self.console:
                self.console.queueEvent(b3.events.Event(b3.events.EVT_CLIENT_NAME_CHANGE, self.name, self))

    def _get_name(self):
        return self._name

    def _get_exactName(self):
        return self._exactName

    name = property(_get_name, _set_name)
    exactName = property(_get_exactName, _set_name)

    #------------------------
    _maxLevel = None
    _maxGroup = None
    def _get_maxLevel(self):
        if self._maxLevel == None:
            if self.groups and len(self.groups):
                m = 0
                for g in self.groups:
                    if g.level > m:
                        m = g.level
                        self._maxGroup = g

                self._maxLevel = m
            elif self._tempLevel:
                self._maxGroup = Group(id=-1, name='Unspecified', level=self._tempLevel)
                return self._tempLevel
            else:
                return 0

        return self._maxLevel

    maxLevel = property(_get_maxLevel)

    def _get_maxGroup(self):
        self._get_maxLevel()
        return self._maxGroup

    maxGroup = property(_get_maxGroup)

    def refreshLevel(self):
        self._maxLevel = None
        self._groups = None

    #------------------------
    def disconnect(self):
        self.console.clients.disconnect(self)

    def kick(self, reason='', keyword=None, admin=None, silent=False, data='', *kwargs):
        self.console.kick(self, reason, admin, silent)

        if self.id:
            ban = ClientKick()
            ban.timeExpire = 0
            ban.clientId = self.id
            ban.keyword = keyword
            ban.data = data

            if admin:
                ban.adminId = admin.id
            else:
                ban.adminId = 0

            ban.reason = reason
            ban.save(self.console)

    def ban(self, reason='', keyword=None, admin=None, silent=False, data='', *kwargs):
        self.console.ban(self, reason, admin, silent)

        if self.id:
            ban = ClientBan()
            ban.timeExpire = -1
            ban.clientId = self.id
            ban.keyword = keyword
            ban.data = data

            if admin:
                ban.adminId = admin.id
            else:
                ban.adminId = 0

            ban.reason = reason
            ban.save(self.console)

    def reBan(self, ban):
        if ban.timeExpire == -1:
            self.console.ban(self, ban.reason, None, True)
        elif ban.timeExpire > self.console.time():
            self.console.tempban(self, ban.reason, int((ban.timeExpire - self.console.time()) / 60), None, True)

    def unban(self, reason='', admin=None, silent=False, *kwargs):
        self.console.unban(self, reason, admin, silent)
        for ban in self.bans:
            ban.inactive = 1
            ban.save(self.console)

    def tempban(self, reason='', keyword=None, duration=2, admin=None, silent=False, data='', *kwargs):
        duration = functions.time2minutes(duration)
        self.console.tempban(self, reason, duration, admin, silent)

        if self.id:
            ban = ClientTempBan()
            ban.timeExpire = self.console.time() + (duration * 60)
            ban.clientId = self.id
            ban.duration = duration
            ban.keyword = keyword
            ban.data = data

            if admin:
                ban.adminId = admin.id
            else:
                ban.adminId = 0

            ban.reason = reason
            ban.save(self.console)

    def message(self, msg):
        self.console.message(self, msg)

    def warn(self, duration, warning, keyword=None, admin=None, data=''):
        if self.id:
            duration = functions.time2minutes(duration)

            warn = ClientWarning()
            warn.timeExpire = self.console.time() + (duration * 60)
            warn.clientId = self.id
            warn.duration = duration
            warn.data = data

            if admin:
                warn.adminId = admin.id
            else:
                warn.adminId = 0

            warn.reason = warning
            warn.keyword = keyword
            warn.save(self.console)

            return warn
        return None

    def notice(self, notice, spare, admin=None):
        if self.id:
            warn = ClientNotice()
            warn.timeAdd = self.console.time()
            warn.clientId = self.id

            if admin:
                warn.adminId = admin.id
            else:
                warn.adminId = 0

            warn.reason = notice
            warn.save(self.console)

    def _get_numWarns(self):
        if not self.id:
            return 0

        return self.console.storage.numPenalties(self, 'Warning')

    numWarnings = property(_get_numWarns)

    def _get_lastWarn(self):
        if not self.id:
            return None

        return self.console.storage.getClientLastPenalty(self, 'Warning')

    lastWarning = property(_get_lastWarn)

    def _get_firstWarn(self):
        if not self.id:
            return None

        return self.console.storage.getClientFirstPenalty(self, 'Warning')

    firstWarning = property(_get_firstWarn)



    def _get_numBans(self):
        if not self.id:
            return 0

        return self.console.storage.numPenalties(self, ('Ban', 'TempBan'))

    numBans = property(_get_numBans)

    def _get_lastBan(self):
        if not self.id:
            return None

        return self.console.storage.getClientLastPenalty(self, ('Ban', 'TempBan'))

    lastBan = property(_get_lastBan)

    def makeAlias(self, name):
        if not self.id or not name:
            return

        try:
            alias = self.console.storage.getClientAlias(Alias(clientId=self.id,alias=name))
        except KeyError:
            alias = None

        if alias:
            if alias.numUsed > 0:
                alias.numUsed += 1
            else:
                alias.numUsed = 1
        else:
            alias = Alias(clientId=self.id, alias=name)

        alias.save(self.console)
        self.console.bot('New alias for %s: %s', str(self.id), alias.alias)

    def save(self, console=None):
        self.timeEdit = time.time()

        if self.guid == None or str(self.guid) == '0':
            # can't save a client without a guid
            return False
        else:
            return self.console.storage.setClient(self)

    def auth(self):
        if not self.authed and self.guid and not self.authorizing:
            self.authorizing = True

            name = self.name
            ip = self.ip
            try:
                inStorage = self.console.storage.getClient(self)
            except KeyError, msg:
                self.console.debug('User not found %s: %s', self.guid, msg)
                inStorage = False
            except Exception, e:
                self.console.error('auth self.console.storage.getClient(client) - %s\n%s', e, traceback.extract_tb(sys.exc_info()[2]))
                self.authorizing = False
                return False

            lastVisit = None
            if inStorage:
                self.console.bot('Client found in storage %s, welcome back %s', str(self.id), self.name)
                lastVisit = self.timeEdit
            else:
                self.console.bot('Client not found in the storage %s, create new', str(self.guid))

            self.connections = int(self.connections) + 1
            self.authed = True
            self.name = name
            self.ip = ip
            self.save()

            self.console.debug('Client Authorized: [%s] %s - %s', self.cid, self.name, self.guid)

            # check for bans
            if self.numBans > 0:
                ban = self.lastBan
                if ban:
                    self.reBan(ban)
                    self.authorizing = False
                    return False

            self.refreshLevel()

            self.console.queueEvent(b3.events.Event(b3.events.EVT_CLIENT_AUTH,
                self,
                self))

            self.authorizing = False

            return self.authed
        else:
            return False

#-----------------------------------------------------------------------------------------------------------------------
class Struct(object):
    def __init__(self, **kwargs):
        for k, v in kwargs.iteritems():
            setattr(self, k, v)

    #------------------------
    _id = 0
    def _set_id(self, v):
        if not v:
            self._id = 0
        else:
            self._id = int(v)

    def _get_id(self):
        return self._id

    id = property(_get_id, _set_id)

#-----------------------------------------------------------------------------------------------------------------------
class Penalty(Struct):
    type = ''
    inactive = 0
    clientId = None
    adminId  = None
    reason = ''
    keyword = ''
    data = ''

    def _set_timeExpire(self, v):
        self._timeExpire = int(v)

    def _get_timeExpire(self):
        return self._timeExpire

    timeExpire = property(_get_timeExpire, _set_timeExpire)

    def _set_timeAdd(self, v):
        self._timeAdd = int(v)

    def _get_timeAdd(self):
        return self._timeAdd

    timeAdd = property(_get_timeAdd, _set_timeAdd)

    def _set_timeEdit(self, v):
        self._timeEdit = int(v)

    def _get_timeEdit(self):
        return self._timeEdit

    timeEdit = property(_get_timeEdit, _set_timeEdit)

    def _set_duration(self, v):
        self._duration = functions.time2minutes(v)

    def _get_duration(self):
        return self._duration

    duration = property(_get_duration, _set_duration)

    def save(self, console):
        self.timeEdit = console.time()

        if not self.id:
            self.timeAdd = console.time()
        return console.storage.setClientPenalty(self)

class ClientWarning(Penalty):
    type = 'Warning'

    def _get_reason(self):
        return self.reason
    def _set_reason(self, value):
        self.reason = value

    warning = property(_get_reason, _set_reason)

class ClientNotice(Penalty):
    type = 'Notice'

    def _get_reason(self):
        return self.reason
    def _set_reason(self, value):
        self.reason = value

    notice = property(_get_reason, _set_reason)

class ClientBan(Penalty):
    type = 'Ban'

class ClientTempBan(Penalty):
    type = 'TempBan'

class ClientKick(Penalty):
    type = 'Kick'

#-----------------------------------------------------------------------------------------------------------------------
class Alias(Struct):
    alias    = ''
    timeAdd  = 0
    timeEdit = 0
    numUsed  = 0
    clientId = 0

    def save(self, console):
        self.timeEdit = console.time()

        if not self.id:
            self.timeAdd = console.time()
        return console.storage.setClientAlias(self)

#-----------------------------------------------------------------------------------------------------------------------
class Group(Struct):
    name    = ''
    keyword = ''
    level    = 0
    timeAdd  = 0
    timeEdit = 0

    def save(self, console):
        self.timeEdit = console.time()

        if not self.id:
            self.timeAdd = console.time()
        return console.storage.setGroup(self)

#-----------------------------------------------------------------------------------------------------------------------
class Clients(dict):
    _nameIndex    = None
    _guidIndex    = None
    _exactNameIndex = None
    _authorizing = False

    console = None

    def __init__(self, console):
        self.console = console
        self._nameIndex    = {}
        self._guidIndex    = {}
        self._exactNameIndex = {}

    def find(self, id, max=None):
        matches = self.getByMagic(id)

        if len(matches) == 0:
            return None
        elif len(matches) > max:
            return matches[0:max]
        else:
            return matches

    def getByName(self, name):
        name = name.lower()

        try:
            return weakref.ref(self[self._nameIndex[name]])()
        except:
            for cid,c in self.items():
                if c.name and c.name.lower() == name:
                    #self.console.debug('Found client by name %s = %s', name, c.name)
                    self._exactNameIndex[name] = c.cid
                    return weakref.ref(c)

        return None

    def getByExactName(self, name):
        name = name.lower() + '^7'

        try:
            c = self[self._exactNameIndex[name]]
            #self.console.debug('Found client by exact name in index %s = %s : %s', name, c.exactName, c.__class__.__name__)
            return weakref.ref(c)()
        except:
            for cid,c in self.items():
                if c.exactName and c.exactName.lower() == name:
                    #self.console.debug('Found client by exact name %s = %s', name, c.exactName)
                    self._exactNameIndex[name] = c.cid
                    return weakref.ref(c)()

        return None

    def getList(self):
        clist = []
        for cid,c in self.items():
            if not c.hide:
                clist.append(weakref.ref(c)())
        return clist

    def getClientsByLevel(self, min=0, max=100, masked=False):
        clist = []
        min, max = int(min), int(max)
        for cid,c in self.items():
            if c.hide:
                continue
            elif not masked and c.maskGroup and c.maskGroup.level >= min and c.maskGroup.level <= max:
                clist.append(weakref.ref(c)())
            elif not masked and c.maskGroup:
                continue
            elif c.maxLevel >= min and c.maxLevel <= max:
                #self.console.debug('getClientsByLevel hidden = %s', c.hide)
                clist.append(weakref.ref(c)())
        return clist

    def getClientsByName(self, name):
        clist = []
        name = name.lower()
        for cid,c in self.items():
            if not c.hide and string.find(c.name.lower(), name) != -1:
                clist.append(weakref.ref(c)())

        return clist

    def getClientLikeName(self, name):
        name = name.lower()
        for cid,c in self.items():
            if not c.hide and string.find(c.name.lower(), name) != -1:
                return weakref.ref(c)()

        return None

    def getClientsByState(self, state):
        clist = []
        for cid,c in self.items():
            if not c.hide and c.state == state:
                clist.append(weakref.ref(c)())

        return clist

    def getByDB(self, id):
        m = re.match(r'^@([0-9]+)$', id)
        if m:
            # seems to be a client db id
            try:
                sclient = self.console.storage.getClientsMatching({ 'id' : m.group(1) })

                if not sclient:
                    return []
                else:
                    clients = []
                    for c in sclient:
                        c.clients = self
                        c.console = self.console
                        c.exactName = c.name
                        clients.append(c)
                        if len(clients) == 5:
                            break

                    return clients
            except:
                return []
        else:
            return self.lookupByName(id)

    def getByMagic(self, id):
        id = id.strip()

        if re.match(r'^[0-9]+$', id):
            # seems to be a client id
            return [self.getByCID(id)]
        elif re.match(r'^@([0-9]+)$', id):
            return self.getByDB(id)
        elif id[:1] == '\\':
            c = self.getByName(id[1:])
            if c and not c.hide:
                return [c]
            else:
                return []
        else:
            return self.getClientsByName(id)

    def getByGUID(self, guid):
        guid = guid.upper()

        try:
            return weakref.ref(self[self._guidIndex[guid]])()
        except:
            for cid,c in self.items():
                if c.guid and c.guid == guid:
                    #self.console.debug('Found client by GUID %s = %s', guid, c.name)
                    self._guidIndex[guid] = c.cid
                    return weakref.ref(c)()

        return None

    def getByCID(self, cid):
        try:
            c = self[str(cid)]
        except KeyError:
            return None
        except Exception, e:
            self.console.error('Unexpected error getByCID(%s) - %s', cid, e)
        else:
            #self.console.debug('Found client by CID %s = %s', cid, c.name)
            if c.cid == str(cid): return weakref.ref(c)()
            else: return None

        return None

    def lookupByName(self, name):
        # first check connected users
        c = self.getClientLikeName(name)
        if c and not c.hide:
            return [c]

        sclient = self.console.storage.getClientsMatching({ '%name%' : name })

        if not sclient:
            return []
        else:
            clients = []
            for c in sclient:
                c.clients = self
                c.console = self.console
                c.exactName = c.name
                clients.append(c)
                if len(clients) == 5:
                    break

            return clients

    def lookupSuperAdmins(self):
        try:
            group = Group(keyword='superadmin')
            group = self.console.storage.getGroup(group)
        except Exception, e:
            self.console.error('^7Could not get superadmin group: %s', e)
            return False

        sclient = self.console.storage.getClientsMatching({ '&group_bits' : group.id })

        if not sclient:
            return []
        else:
            clients = []
            for c in sclient:
                c.clients = self
                c.console = self.console
                c.exactName = c.name
                clients.append(c)
 
            return clients

    def disconnect(self, client):
        client.connected = False
        if client.cid == None:
            return

        cid = str(client.cid)
        if self.has_key(cid):
            self[cid] = None
            del self[cid]
            del client
            self.console.queueEvent(b3.events.Event(b3.events.EVT_CLIENT_DISCONNECT, cid))

        self.resetIndex()

    def resetIndex(self):
        # reset the indexes
        self._nameIndex    = {}
        self._guidIndex    = {}
        self._exactNameIndex = {}

    def newClient(self, cid, **kwargs):
        client = Client(console=self.console, cid=cid, timeAdd=self.console.time(), **kwargs)
        self[client.cid] = client
        self.resetIndex()

        self.console.debug('Client Connected: [%s] %s - %s (%s)', self[client.cid].cid, self[client.cid].name, self[client.cid].guid, self[client.cid].data)

        self.console.queueEvent(b3.events.Event(b3.events.EVT_CLIENT_CONNECT,
            client,
            client))
    
        if client.guid:
            client.auth()
        elif not client.authed:
            self.authorizeClients()

    def empty(self):
        self.clear()

    def clear(self):
        self.resetIndex()
        for cid,c in self.items():
            if cid != '-1':
                del self[cid]

    def sync(self):
        plist = self.console.getPlayerList()
        mlist = {}

        for cid, c in plist.iteritems():
            client = self.getByCID(cid)
            if client:
                if client.haskey('guid'):
                    if client.guid == c['guid']:
                        # player matches
                        self.console.debug('in-sync %s == %s', client.guid, c['guid'])
                        mlist[str(cid)] = client
                    else:
                        self.console.debug('no-sync %s <> %s', client.guid, c['guid'])
                        client.disconnect()
                elif client.has_key('ip'):
                    if client.ip == c['ip']:
                        # player matches
                        self.console.debug('in-sync %s == %s', client.ip, c['ip'])
                        mlist[str(cid)] = client
                    else:
                        self.console.debug('no-sync %s <> %s', client.ip, c['ip'])
                        client.disconnect()
                else:
                    self.console.debug('no-sync: no guid or ip found.')


        # remove existing clients
        self.clear()

        # add list of matching clients
        for cid, c in mlist.iteritems():
            self[str(cid)] = c

    def authorizeClients(self):
        if not self._authorizing:
            # lookup is delayed to allow time for auth
            # it will also allow us to batch the lookups if several players
            # are joining at once
            self._authorizing = True
            t = threading.Timer(5, self._authorizeClients)
            t.start()

    def _authorizeClients(self):
        self._authorizing = False

        players = self.console.getPlayerList()
        self.console.verbose('Clients._authorizeClients() = %s' % players)

        for cid, p in players.iteritems():
            sp = self.getByCID(cid)
            if sp:
                sp.ip   = p['ip']
                sp.pbid = p['pbid']
                sp.guid = p['guid']
                sp.data = p
                sp.auth()
