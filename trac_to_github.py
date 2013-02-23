from github import Github
from github import Issue
from github import GithubObject
from urlparse import urlparse
import yaml
import os.path
import xmlrpclib
import socket
import re
import urllib
import pickle

# just a simple intermediary object
# too lazy to use @property decorators
class TracTicket():
    def __init__(self):
        self.trac_id = -1
        self.summary = ""
        self.status = ""
        self.resolution = ""
        self.description = ""
        self.milestone = None
        self.owner = ""
        self.time = None
        self.changedTime = None
        self.issueType = ""
    
    def to_string(self, verbose=False):
        if verbose:
            return """Summary: {0.summary}\nStatus: {0.status}\nResolution: {0.resolution}
Description: {0.description}\nMilestone: {0.milestone}\nOwner: {0.owner}\nTime: {0.time}
ChangedTime: {0.changedTime}\nIssueType: {0.issueType}\n""".format(self)
        else:
            return """Status: {0.status}\nResolution: {0.resolution}
Milestone: {0.milestone}\nOwner: {0.owner}\nTime: {0.time}
ChangedTime: {0.changedTime}\nIssueType: {0.issueType}\n""".format(self)

# read trac ticket data via XMLRPC
class TracTicketReader(object):
    def __init__(self, config):
        self.config = config
        self._tickets = []
    
    @property
    def tickets(self):
        return self._tickets
    
    def read_trac_data(self):
        print "Reading Trac data"
        
        xmlrpc = self.xmlrpc_login()
        all_ticket_ids = xmlrpc.ticket.query('status=new|closed|assigned|reopened')
        
        print "Found {0} Trac tickets".format(len(all_ticket_ids))
        
        for ticket_id in all_ticket_ids:
            print "Reading ticket #{0}".format(ticket_id)
            ticket_data = xmlrpc.ticket.get(ticket_id)
            self.create_ticket(ticket_data)
    
    def xmlrpc_login(self):
        socket.setdefaulttimeout(30)
    	match = re.match('(\w+)://(?:[^@\s]+@)?([^@\s]+)$', self.config['trac-server'])
    	if not match:
    		sys.exit("Error: Invalid server URL '{0}'".format(self.config['trac-server']))
    	# url = match.group(1)+'://'+user+':'+urllib.quote(config['password'])+'@'+match.group(2)+'/login/xmlrpc'
        url = "{protocol}://{user}:{password}@{path}/{project}/login/xmlrpc".format(
            protocol = match.group(1), 
            user = self.config['trac-login'],
            password = urllib.quote(self.config['trac-password']),
            path = match.group(2),
            project = self.config['trac-project'])
    	xmlrpc = xmlrpclib.ServerProxy(url)
    	return xmlrpc
        
    def create_ticket(self, data):
        ticket = TracTicket()
        info = data[3] # the important stuff seems to be a dictionary in the 3rd array item
        # filter through info and get the stuff we care about
        ticket.status = info['status']
        ticket.changedTime = info['changetime']
        ticket.type = info['type']
        ticket.description = info['description']
        ticket.milestone = info['milestone']
        ticket.summary = info['summary']
        ticket.priority = info['priority']
        ticket.owner = info['owner']
        ticket.time = info['time']
        ticket.resolution = info['resolution']
        ticket.trac_id = data[0]
        self._tickets.append(ticket)

# collect issues and submit to github
class GithubIssueSubmitter(object):
    def __init__(self, config):
        self.config = config
        self._issues = [] # github issues
        self._milestones = {} # key-value dict
        self.login_to_github()
        self.index_milestones()
    
    def login_to_github(self):
        print "Logging into Github"
        ghub = Github(self.config['github-login'], self.config['github-password'])
        org = ghub.get_organization(self.config['github-organization'])
        self.repo = org.get_repo(self.config['github-project'])
        print "Found repository: {0}".format(self.repo.name)
    
    def index_milestones(self):
        # index existing milestones so we don't re-create them
        for m in self.repo.get_milestones():
            self._milestones[m.title] = m
        # the default get_milestones does not return closed milestones
        for m in self.repo.get_milestones(state='closed'):
            self._milestones[m.title] = m
    
    @property
    def issues(self):
        return self._issues
    
    def import_trac_tickets(self, tickets):
        import_count = 0
        ignore_count = 0
        for ticket in tickets:
            print """Importing ticket #{0}: "{1}" """.format(ticket.trac_id, ticket.summary)
            
            do_import = True
            
            if self.config['check-duplicates'] or self.config['ignore-duplicates']:
                if self.check_duplicates(ticket.summary):
                    if self.config['ignore-duplicates']:
                        do_import = False
                    elif self.config['check-duplicates']:
                        ans = raw_input("A duplicate issue was found; create anyway? [y/n] ")
                        if ans.lower() == "n":
                            do_import = False
            
            if do_import:
                self.create_issue(ticket)
                import_count += 1
            else:
                ignore_count += 1
                print """Ignoring duplicate issue "{0}" """.format(ticket.summary)
        
        print "Successfully imported {0} tickets (ignored {1} duplicates)".format(import_count, ignore_count)
    
    def check_duplicates(self, title):
        for issue in self.repo.get_issues():
            if issue.title == title:
                return True
        for issue in self.repo.get_issues(state='closed'):
            if issue.title == title:
                return True
        return False
    
    def create_issue(self, ticket):
        milestone = self.get_milestone(ticket.milestone)
        if milestone == None:
            milestone = GithubObject.NotSet
        # create_issue( title, [body, assignee, milestone, labels] )
        issue = self.repo.create_issue(ticket.summary, body = ticket.description, milestone = milestone)
        
        state = "closed" if ticket.status == "closed" else "open" # trac has more words for 'open' than github
        issue.edit(state=state)
        self._issues.append(issue)
        orig_url = "{server}/ticket/{id}".format(server = self.config['trac-server'], id = ticket.trac_id)
        comment = "Imported from Trac\nURL: {0}\n{1}".format(orig_url, ticket.to_string())
        issue.create_comment(comment)
        
    def get_milestone(self, milestone_name):
        if len(milestone_name.strip()) == 0:
            return None
        
        if not(milestone_name in self._milestones.keys()):
            print "Creating milestone {0}".format(milestone_name)
            self._milestones[milestone_name] = self.repo.create_milestone(milestone_name)
        return self._milestones[milestone_name]


# read pickled data
def read_from_file(filepath):
    infile = open(filepath, 'rb')
    obj = pickle.load(infile)
    infile.close()
    return obj
    
# write pickled data
def store_to_file(filepath, obj):
    outfile = open(filepath, 'wb')
    pickle.dump(obj, outfile)
    outfile.close()
    
def verify_config(config):
    print "Verifying configuration file..."
    looks_ok = True
    if config['github-organization'] == '':
        print "\tMissing github-organization"
        looks_ok = False
    
    if config['github-project'] == '':
        print "\tMissing github-project"
        looks_ok = False
    
    if config['trac-server'] == '':
        print "\tMissing trac-server"
        looks_ok = False
    
    if config['trac-project'] == '':
        print "\tMissing trac-project"
        looks_ok = False
    
    if config['github-login'] == '':
        print "\tMissing github-login"
        looks_ok = False
    
    if config['github-password'] == '':
        print "\tMissing github-password"
        looks_ok = False
    
    if config['trac-login'] == '':
        print "\tMissing trac-login"
        looks_ok = False
    
    if config['trac-password'] == '':
        print "\tMissing trac-password"
        looks_ok = False

    if looks_ok:
        print "Looks ok"
    return looks_ok

def main():
    config_file = os.path.join(os.path.dirname(__file__), 'config.yaml')
    
    f = open(config_file)
    config = yaml.load(f.read())
    f.close()
    
    if verify_config(config) == False:
        print "Exiting (fix your config.yaml file)"
        exit(1)
    
    cache_file = os.path.join(os.path.dirname(__file__), '{0}.pickle'.format(config['trac-project']))
    cache_exists = os.path.isfile(cache_file)
    
    # cache the trac data to make it faster in case something goes wrong during the github import
    if cache_exists:
        print "Reading Trac data from cache {0}".format(cache_file)
        ticket_reader = read_from_file(cache_file)
    else:
        ticket_reader = TracTicketReader(config)
        ticket_reader.read_trac_data()
        print "Saving Trac data to cache in case something goes wrong {0}".format(cache_file)
        store_to_file(cache_file, ticket_reader)
    
    github_submitter = GithubIssueSubmitter(config)
    github_submitter.import_trac_tickets(ticket_reader.tickets)

if __name__ == '__main__':
    main()