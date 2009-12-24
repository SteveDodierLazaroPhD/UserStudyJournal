import dbus
import dbus.service



class TeamgeistInterface(object):
	def __init__(self):
		TEAMGEIST_SERVICE = "/org/gnome/zeitgeist/teamgeist"
		TEAMGEIST_INTERFACE = 					"org.gnome.zeitgeist.Teamgeist"
		TEAMGEIST_ACCOUNT_INTERFACE = "org.gnome.zeitgeist.Teamgeist.Interfaces.Account"
		
		bus = dbus.SessionBus ()
		
		obj = bus.get_object (TEAMGEIST_INTERFACE, TEAMGEIST_SERVICE)
		self.teamgeist_iface = dbus.Interface (obj, TEAMGEIST_INTERFACE)
		
		obj1 = bus.get_object (TEAMGEIST_INTERFACE, TEAMGEIST_SERVICE)
		self.account_iface = dbus.Interface(obj1, TEAMGEIST_ACCOUNT_INTERFACE)
		
	def ListTeamTypes(self):
		team_types = self.teamgeist_iface.ListTeamTypes()
		print "--------------------------------------------"
		for type in team_types:
			print type
		
	def ListTeams(self):
		teams = self.teamgeist_iface.ListTeams()
		print "--------------------------------------------"
		for team in teams:
			print team
		
	def ListAccounts(self):
		accounts = self.teamgeist_iface.ListAccounts()
		return accounts
			
	def GetDisplayName(self, account):
		return self.account_iface.GetDisplayName(account)
			
	def GetTeams(self):
		#teams = self.ListTeamTypes()
		accs = self.ListAccounts()
		accounts = []
		for acc in accs:
			try:
				name = self.GetDisplayName(acc)
				#print acc
				accounts.append({"name":name, "acc":acc})
			except:
				pass
		return accounts

if __name__=="__main__":
	teamgeist = TeamgeistInterface()
	#teamgeist.ListTeamTypes()
	#teamgeist.ListTeams()
	teamgeist.GetTeams()