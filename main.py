#!/usr/bin/env python

# Python libraries
import os
import cgi
import urllib
import json

# Google App Engine api
from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.api import mail

# Web libraries
import webapp2
import jinja2

JINJA_ENVIRONMENT = jinja2.Environment(
	loader = jinja2.FileSystemLoader(os.path.dirname(__file__)),
	extensions = ['jinja2.ext.autoescape']
)

class Item(ndb.Model):
	name = ndb.StringProperty(required=True)
	item_type = ndb.StringProperty(required=True, choices=['Book', 'Electronic Product', 'Stationery', 'Other'])
	description = ndb.StringProperty(indexed=False)
	origin_price = ndb.IntegerProperty(required=True)
	start_price = ndb.IntegerProperty(required=True)
	current_price = ndb.IntegerProperty(required=True)
	buyer_num = ndb.IntegerProperty(default=0)
	current_buyer = ndb.StringProperty(required=True)
	picture = ndb.StringProperty(indexed=False)
	confirmed = ndb.BooleanProperty(default=False)

class MainHandler(webapp2.RequestHandler):
	def get(self):
		# # admin
		# if not users.is_current_user_admin():
		# 	self.redirect('/sorry')
		# user
		user = users.get_current_user()
		if user:
			user_url = users.create_logout_url(self.request.uri)
			user_url_linktext = 'Logout'
			# admin
			isAdmin = users.is_current_user_admin()
			# items
			items = Item.query(Item.confirmed == False).order(-Item.buyer_num).fetch(100)
			my_confirmed_items = Item.query(ndb.AND(
				Item.confirmed == True,
				Item.current_buyer == user.email()
				)).fetch(100)
			my_items = []
			my_total_price = 0
			# stat
			stat = {
				'item_num': len(items),
				'item_sold': 0,
				'item_total_buyer': 0
			}
			for item in items:
				if item.current_buyer == user.email():
					item.is_mine = True
					my_items.append(item)
					my_total_price += item.current_price
				item.is_hot = bool(item.buyer_num >= 5)
				item.is_free = bool(item.current_price == 0)
				if item.current_buyer:
					stat['item_sold'] += 1
				stat['item_total_buyer'] += item.buyer_num

			if not stat['item_num']:
				stat['item_ratio'] = 0
			else:
				stat['item_ratio'] = float(stat['item_sold']) / float(stat['item_num']) * 100

			template_values = {
				'stat': stat,
				'items': items,
				'my_confirmed_items': my_confirmed_items,
				'has_items': bool(len(my_items) + len(my_confirmed_items)),
				'my_items': my_items,
				'my_total_price': my_total_price,
				'user': user,
				'user_url': user_url,
				'user_url_linktext': user_url_linktext,
				'isAdmin': isAdmin
			}
		else:
			user_url = users.create_login_url(self.request.uri)
			user_url_linktext = 'Login'
			# admin
			isAdmin = users.is_current_user_admin()
			# items
			items = Item.query().fetch(100)
			# stat
			stat = {
				'item_num': len(items),
				'item_sold': 0,
				'item_total_buyer': 0
			}

			for item in items:
				if item.current_buyer:
					stat['item_sold'] += 1
				stat['item_total_buyer'] += item.buyer_num

			if not stat['item_num']:
				stat['item_ratio'] = 0
			else:
				stat['item_ratio'] = float(stat['item_sold']) / float(stat['item_num']) * 100

			template_values = {
				'stat': stat,
				'user': user,
				'user_url': user_url,
				'user_url_linktext': user_url_linktext,
				'isAdmin': isAdmin
			}

		template = JINJA_ENVIRONMENT.get_template('index.html')
		self.response.write(template.render(template_values))

class SorryHandler(webapp2.RequestHandler):
	def get(self):
		# admin
		self.response.write('Sorry, under development. -- Ming');
		self.response.write('<a href="' + users.create_login_url(self.request.uri) + '">LOGIN</a>');

class ConfirmHandler(webapp2.RequestHandler):
	def get(self):
		# user
		user = users.get_current_user()
		if not user:
			self.redirect('/')
		else:
			items = Item.query(ndb.AND(
				Item.confirmed == False,
				Item.current_buyer == user.email())).fetch(100)
			if not len(items):
				self.redirect('/')
			else:
				for item in items:
					item.confirmed = True
					item.put()
				s = '''
	Dear %s, 
	Thank you for using my website.
	You need to pay the following amount of money: $ %s.
	Please reply this email ASAP (arranging pick up time)!!!

	Best regards,
	Ming
	''' % (user.nickname(), sum([item.current_price for item in items]))
				s.encode(encoding='UTF-8',errors='strict')
				mail.send_mail(
					sender='Ming YIN <ym.kalasoo@gmail.com>',
					to=user.email(),
					subject='sellmystuffym Notification',
					body=s
					)
				self.redirect('/')

class AddConfirmHandler(webapp2.RequestHandler):
	def get(self):
		# admin
		if not users.is_current_user_admin():
			self.redirect('/')
		# items
		items = Item.query().order(-Item.buyer_num).fetch(100)
		for item in items:
			item.confirmed = False
			item.put()
		self.redirect('/')

class SendMailHandler(webapp2.RequestHandler):
	def get(self):
		# admin
		if not users.is_current_user_admin():
			self.redirect('/')
		# items
		items = Item.query(Item.confirmed == False).fetch(100)
		emails = list(set([ item.current_buyer for item in items ]))
		template_values = {
			'emails': emails
		}
		template = JINJA_ENVIRONMENT.get_template('sendmail.html')
		self.response.write(template.render(template_values))

	def post(self):
		# admin
		if not users.is_current_user_admin():
			self.redirect('/')
		# items
		items = Item.query(Item.confirmed == False).fetch(100)
		emails = list(set([ item.current_buyer for item in items ]))

		subject = self.request.get('email_title') or 'sellmystuffym Notification'
		content = self.request.get('email_content')
		if not content:
			self.redirect('/send_mail')
		else:
			for email in emails:
				if not email:
					continue
				s = '''
Dear %s, 
''' % email + content + '''
Best regards,
Ming
'''
				print s
				mail.send_mail(
					sender='Ming YIN <ym.kalasoo@gmail.com>',
					to=email,
					subject=subject,
					body=s
					)
			self.redirect('/send_mail')


class ImageHandler(webapp2.RequestHandler):
	def get(self):
		item = ndb.get(self.request.get('img_id'))
		if item.picture:
			self.response.out.write(greeting.picture)

class AddItemHandler(webapp2.RequestHandler):
	def get(self):
		# admin
		if not users.is_current_user_admin():
			self.redirect('/')
		template_values = {

		}
		template = JINJA_ENVIRONMENT.get_template('addItem.html')
		self.response.write(template.render(template_values))

	def post(self):
		# admin
		if not users.is_current_user_admin():
			self.redirect('/')
		# new item instance
		item = self.gen_Item()
		if not item:
			self.redirect('/add_item')
		else:
			item.put()
			self.redirect('/')
		self.response.write(item)

	def gen_Item(self):
		req = self.request
		name = req.get('item_name')
		item_type = req.get('item_type')
		description = req.get('item_desc')
		origin_price = req.get('origin_price')
		start_price = req.get('start_price')
		current_price = start_price
		buyer_num = 0
		current_buyer = ""
		picture = req.get('picture')
		# check
		if not all([name, item_type, origin_price, start_price]):
			return None
		else:
			origin_price = int(origin_price)
			start_price = int(start_price)
			current_price = int(current_price)
			print picture
			item = Item(
				name=name,
				item_type=item_type,
				description=description,
				origin_price=origin_price,
				start_price=start_price,
				current_price=current_price,
				buyer_num=buyer_num,
				current_buyer=current_buyer,
				picture=picture
				)
			return item

class WantBuyHandler(webapp2.RequestHandler):
	def post(self):
		res = {
			'done': False,
			'current_price': 0
		}
		# user
		user = users.get_current_user()
		if not user:
			res['error'] = 'user'
			self.response.write(json.dumps(res))
			return
		# item
		item = Item.get_by_id(int(self.request.get('item_id')))
		if not item:
			res['error'] = 'item'
			self.response.write(json.dumps(res))
			return

		if item.start_price:
			if user.email() != item.current_buyer:
				item.current_buyer = user.email()
				item.current_price += 1
				item.buyer_num += 1
		else:
			if not item.current_buyer:
				item.current_buyer = user.email()
				item.buyer_num += 1
			elif user.email() != item.current_buyer:
				res['error'] = 'free'
				self.response.write(json.dumps(res))
				return

		res['current_price'] = item.current_price
		item.put()
		res['done'] = True
		# return
		self.response.write(json.dumps(res))

app = webapp2.WSGIApplication([
	('/', MainHandler),
	('/sorry', SorryHandler),
	('/confirm', ConfirmHandler),
	('/add_confirm', AddConfirmHandler),
	('/send_mail', SendMailHandler),
	('/img', ImageHandler),
	('/add_item', AddItemHandler),
	('/want_buy', WantBuyHandler)
], debug=True)
