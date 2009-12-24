'''
Created on Nov 28, 2009

@author: seif
'''
import gtk
from view import Portal
from model import Model


if __name__ == '__main__':    
    model = Model()
    portal = Portal(model)
    gtk.main()
    