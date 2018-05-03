#!/usr/bin/python3
################################################################################
#   The Scrum simulator
################################################################################

import math
import abc
import argparse
import json
from enum import Enum, auto

'''
new -> ready -> active -> resolved -> deployed-> closed -> good -> live
                    ^                  |          |
                    |                  |          |
                    +------------------+----------+
'''

class Journal:

    def print( self, *args, **kwargs ):
        print( 'JOURNAL', *args, **kwargs )

J = Journal()

PICK_SMALLER_STORY_FIRST_POLICY = False

class System:

    def __init__( self, args ):
        self._logons = set()
        self._available = True

    def setLock( self, lock=True ):
        self._available = not( lock )
        if lock:
            self._logons.clear()

    def logon( self, username ):
        if self._available:
            self._logons.add( username )
        else:
            raise Exception( 'System down' )

    def logoff( self, username ):
        if self._available:
            self._logons.remove( username )
        else:
            raise Exception( 'System down' )

    def hasLogons( self ):
        return bool( self._logons )

    def isAvailable( self ):
        return self._available

class Transitions:
    '''Defines the matrix of transition probabilities on work done'''

    def __init__( self, args ):
        self._args = args

    def transition( self, status ):
        pass


class UserStory:

    def __init__( self, title='Anon User Story', points=1, status='active', work_profile={}, factory=None ):
        self._title = title
        self._points = points
        self._status = status
        self._initial_profile = work_profile
        self._remaining = work_profile.copy()
        self._assigned_to = None
        self._factory = factory

    def __str__( self ):
        return self._title

    def show( self ):
        J.print( 'Story {} {}; assigned {}; remaining {}'.format( self._title, self._status, self._assigned_to, self._remaining ) )

    def isAssignedTo( self, x ):
        return self._assigned_to == x

    def hasStatus( self, *statuses ):
        return self._status in statuses

    def currentStatus( self ):
        return self._status

    def isActive( self ):
        return self._status == 'active'

    def isResolved( self ):
        return self._status == 'resolved'

    def isUnassigned( self ):
        return self._assigned_to is None

    def assignTo( self, x ):
        self._assigned_to = x
        J.print( 'Assigning story {} to {}'.format( self, x ) )
        return self

    def progress( self, work_done, next_status ):
        self._remaining[ self._status ] -= work_done
        # print( 'Remaining', self._status, self._remaining[ self._status ] )
        if self._remaining[ self._status ] <= 0:
            self._status = next_status
            self._assigned_to = None

    def pickMeBefore( self, them ):
        return ( self._points < them._points ) == PICK_SMALLER_STORY_FIRST_POLICY

class UserStoryFactory:

    def __init__( self, pointsToHours ):
        self._pointsToHours = pointsToHours

    def new( self, **kwargs ):
        if not 'work_profile' in kwargs:
            kwargs[ 'work_profile' ] = self._pointsToHours( kwargs[ 'points' ] )
        return UserStory( factory=self, **kwargs )

class PointsToHours:
    '''We're going to need some kind of adaptive response, so
    this class can use the args to find out the curve needed.'''

    def __init__( self, args ):
        self._args = args

    def __call__( self, npoints ):
        base = npoints * 7
        return { 'active': base, 'resolved': 1, 'deployed': math.ceil( base * 0.6 ) }

class Backlog:

    def __init__( self, args ):
        self._args = args
        self._user_story_factory = self._args.user_story_factory
        self._stories = [ self._user_story_factory.new( **jstory ) for jstory in json.load( args.backlog ) ]  #, {'points': 2}, {'points': 5}, {'points': 8} ]

    def show( self ):
        for story in self._stories:
            story.show()

    def __iter__( self ):
        return iter( self._stories )

    def findStories( self, test_status=None, assigned=None ):
        for story in self._stories:
            if story.isAssignedTo( assigned ):
                if test_status is None or test_status( story.currentStatus() ):
                    yield story   

class MemberOfTechnicalStaff:

    def __init__( self, name, *capabilities ):
        self._name = name
        self._busy = None
        self._capabilities = [ *capabilities ]

    def name( self ):
        return self._name

    def isBusy( self ):
        return bool( self._busy )

    def setBusy( self, busy=None ):
        self._busy = busy

    def add( self, capability ):
        self._capabilities.append( capability )


class Capability:

    category = 'Staff'

    def __init__( self, name=None, capability=None ):
        self._mots = None
        if name:
            self._mots = MemberOfTechnicalStaff( name )
        if capability:
            self._mots = capability._mots
        if not self._mots:
            raise Exception( 'Invalid initial parameters' )
        self._on_story = None
        self._mots.add( self )

    def name( self ):
        return self._mots.name()

    def isOnStory( self ):
        return bool( self._on_story )

    def setOnStory( self, story=None ):
        self._on_story = story
        self._mots.setBusy( busy=story and self )

    def onStory( self ):
        return self._on_story

    def __str__( self ):
        return '{}({})'.format( self.name(), self.category )

    def productivity( self ):
        return 1

    def assignStoryFromBacklog( self, backlog, system ):
        pick = None
        for story in backlog.findStories( test_status=self.acceptStatus ):
            if self.areResourcesAvailable( system ):
                if not pick or story.pickMeBefore( pick ):
                    pick = story
        if pick:
            self.reserveResources( system )
            self.setOnStory( story = pick )
            pick.assignTo( self )
            return pick
        
    def grabNextStory( self, backlog, system ):
        story = self.onStory()
        if story:
            return story
        if self._mots.isBusy():
            return None
        story = self.assignStoryFromBacklog( backlog, system )
        if story:
            return story

    def progressOneHour( self, story ):
        next_status = self.nextStatus( story.currentStatus() )
        story.progress( self.productivity(), next_status )
        # print( 'Compare', story._status, next_status )
        if story.hasStatus( next_status ):
            J.print( '{} completes work on "{}"'.format( self, story ) )
            return True
        return False

    def jobDone( self, system ):
        self.setOnStory( story = None )
        self.releaseResources( system )

    def areResourcesAvailable( self, system ):
        return True

    def reserveResources( self, system ):
        pass

    def releaseResources( self, system ):
        pass

    @abc.abstractmethod
    def acceptStatus( self ):
        raise Exception()

    @abc.abstractmethod
    def nextStatuses( self ):
        raise Exception()

class Developer( Capability ):

    category = 'Dev'

    def __init__( self, **kwargs ):
        super().__init__( **kwargs )

    # def initialStatuses( self ):
    #     return [ 'active' ]

    def acceptStatus( self, x ):
        return x == 'active'

    def nextStatus( self, _x ):
        return 'resolved'

class Ops( Capability ):

    category = 'Ops'

    def __init__( self, **kwargs ):
        super().__init__( **kwargs )

    def acceptStatus( self, x ):
        return x == 'resolved'

    def nextStatus( self, x ):
        return 'deployed'

    def areResourcesAvailable( self, system ):
        # print( 'areResourcesAvailable', 'available', system.isAvailable() )
        # print( 'areResourcesAvailable', 'hasLogons', system.hasLogons() )
        return system.isAvailable() and not( system.hasLogons() )

    def reserveResources( self, system ):
        # print( 'Locking the system' )
        return system.setLock( lock = True )

    def releaseResources( self, system ):
        # print( 'Unlocking the system' )
        return system.setLock( lock = False )

class QA( Capability ):

    category = 'QA'

    def __init__( self, **kwargs ):
        super().__init__( **kwargs )

    def acceptStatus( self, x ):
        return x == 'deployed'

    def nextStatus( self, _x ):
        return 'closed'

    def areResourcesAvailable( self, system ):
        return system.isAvailable()

    def reserveResources( self, system ):
        return system.logon( self.name() )

    def releaseResources( self, system ):
        return system.logoff( self.name() )


class Assignment:

    def __init__( self, capability, backlog, system ):
        self._capability = capability
        self._backlog = backlog
        self._system = system
        self._story = None
        self._done = False

    def markWorkAsDone( self ):
        self._done = True

    def grabNextStory( self ):
        story = self._capability.grabNextStory( self._backlog, self._system )
        self._story = story 
        return story

    def progressOneHour( self ):
        self._done = self._capability.progressOneHour( self._story )

    def endOfHour( self, system ):
        if self._done:
            self._capability.jobDone( system )


class Team:

    def __init__( self, args ):
        self._args = args
        alpha1 = Developer( name='Alpha' )
        beta2 = QA( name='Beta' )
        alpha3 = Ops( capability=alpha1 )
        self._members = [ alpha1, beta2, alpha3 ]

    def __iter__( self ):
        return iter( self._members )

    def __str__( self ):
        return ', '.join( str( x ) for x in self._members )

class DevQASystem:

    def __init__( self ):
        self._available = False

    def takeSystemDown( self ):
        self._available = False

    def bringSystemUp( self ):
        self._available = True

    def isSystemAvailable( self ):
        return self._available

class Scrumulation:

    def __init__( self, team, backlog, system ):
        self._team = team
        self._backlog = backlog
        self._system = system

    def scrumulateOneHour( self ):
        assignments = []
        for cap in self._team:
            A = Assignment( cap, self._backlog, self._system )
            if A.grabNextStory():
                assignments.append( A )
        for assignment in assignments:
            assignment.progressOneHour()
        for assignment in assignments:
            assignment.endOfHour( self._system )
        return bool( assignments )

    def scrumlate( self ):
        count = 0
        while True:
            count += 1
            for hour in range( 1, 8 ):
                if not self.scrumulateOneHour():
                    return
            J.print( '--- Day', count, 'Hour', hour ) 
            self._backlog.show()

class Main:

    def __init__( self, args ):
        self._args = args
        self._args.user_story_factory = UserStoryFactory( PointsToHours( args ) )
        self._backlog = Backlog( args )
        self._team = Team( args )
        self._system = System( args )

    def scrumlate( self ):
        self._scrumlation = Scrumulation( self._team, self._backlog, self._system )
        self._scrumlation.scrumlate()

    def ruler( self ):
        J.print( '-' *  80 )

    def run( self ):
        J.print( 'Scrumulation initial conditions' )
        self._backlog.show()
        self.ruler()
        J.print( self._team )
        J.print( 'Begin scrumulation' )
        self.scrumlate()
        self.ruler()
        self._backlog.show()
        J.print( 'End scrumulation' )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument( "--backlog", type=argparse.FileType('r'), default='backlog.json', help="Backlog in JSON format" )
    # parser.add_argument( "--full", action='store_true', default=False, help="Scan all possible values" )
    # parser.add_argument( "--fuzz", type=int, default=0, help="Fuzztest N values" )
    # parser.add_argument( "--exactonly", action='store_true', default=False, help="Exclude non-exact triples" )    
    MAIN = Main( parser.parse_args() )
    MAIN.run()
