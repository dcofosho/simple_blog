import os
import webapp2
from google.appengine.ext import db, ndb
import datetime
import jinja2
import string
import hashlib
import uuid
import re

jinja_environment = jinja2.Environment(
    autoescape=True, loader=jinja2.FileSystemLoader(
        os.path.join(os.path.dirname(__file__), 'templates')))


# Error strings for template errors
username_error = "Invalid username"
username_blank = "Enter a username"
password_error = "Enter a valid password"
password_blank = "Enter a password"
verification_error = "Passwords do not match"
email_error = "Enter a valid email address"

USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
PASS_RE = re.compile(r"^.{3,20}$")
EMAIL_RE = re.compile(r"^[\S]+@[\S]+.[\S]+$")


def valid_password(password):
    '''validates entered password'''
    return PASS_RE.match(password)


def valid_username(username):
    '''validates entered username'''
    return USER_RE.match(username)


def valid_email(email):
    '''validates email'''
    return EMAIL_RE.match(email)

# User database model


class Users(db.Model):
    username = db.StringProperty(required=True)
    password_hash = db.StringProperty(required=True)
    salt = db.StringProperty(required=True)
    email = db.EmailProperty(required=False)

# Comments database model


class Comment_db(db.Model):
    post_id = db.StringProperty()
    created_by = db.StringProperty()
    text = db.TextProperty()
    date_created = db.DateTimeProperty(auto_now_add=True)

# Blog post database model


class BlogPost_db(db.Model):
    subject = db.StringProperty()
    content = db.TextProperty()
    liked_by = db.ListProperty(str, default=[])
    disliked_by = db.ListProperty(str, default=[])
    created_by = db.StringProperty()
    date_created = db.DateTimeProperty(auto_now_add=True)


def hashed_key(key, salt=None):
    ''' Takes a key and salt as arguments and return a hashed string'''
    if not salt:
        salt = uuid.uuid4().hex
    hashed_key = hashlib.sha512(key + salt).hexdigest()
    return "%s|%s" % (hashed_key, salt)


def gen_user_cookie(user_id):
    '''Generates hashed user cookie string from user id
     using a secret key #xadahiya'''
    hashed_user_id = hashed_key(user_id, "pluut0nniwm469").split("|")[0]
    return "%s|%s" % (user_id, hashed_user_id)


def validate_user_cookie(user_cookie):
    ''' validates a user cookie string and returns a user'''
    user_id, user_id_hash = user_cookie.split("|")
    if hashed_key(user_id, "pluut0nniwm469").split("|")[0] == user_id_hash:
        return Users.get_by_id(int(user_id))
    else:
        return None


class AuthenticatorHandler(webapp2.RequestHandler):

    def get(self):
        self.response.headers['Content-Type'] = 'text/html'
        template_values = {}

        template = jinja_environment.get_template('signup.html')
        self.response.out.write(template.render(template_values))

    def post(self):
        # Username validation
        template_values = {}
        try:
            username = self.request.get("username")
            if not (username and valid_username(username)):
                template_values['username_error'] = username_error
        except:
            template_values['username_error'] = username_blank

        # Password validation
        try:
            password = self.request.get("password")
            verify = self.request.get("verify")
            if not (password and valid_password(password)):
                template_values['password_error'] = password_error
            elif password != verify:
                template_values['verification_error'] = verification_error
        except:
            template_values['password_error'] = password_blank

        # Email validation
        email = self.request.get("email")
        if email:
            if not valid_email(email):
                template_values['email_error'] = email_error

        if template_values:
            template = jinja_environment.get_template('signup.html')
            self.response.out.write(template.render(template_values))
        else:
            pass_hash_str = hashed_key(password)
            pass_hash, salt = pass_hash_str.split("|")
            print pass_hash, salt
            if email:
                user = Users(username=username,
                             password_hash=pass_hash, salt=salt, email=email)
                user_key = user.put()
                user_id = str(user_key.id())
            else:
                user = Users(username=username,
                             password_hash=pass_hash, salt=salt)
                user_key = user.put()
                user_id = str(user_key.id())

            user_cookie_str = gen_user_cookie(user_id)
            self.response.headers.add_header(
                'Set-Cookie', 'userid = %s; Path=/' % user_cookie_str)

            self.redirect("/user/welcome")


class LoginHandler(webapp2.RequestHandler):

    def get(self):
        self.response.headers['Content-Type'] = 'text/html'
        template_values = {}
        template = jinja_environment.get_template('login.html')
        self.response.out.write(template.render(template_values))

    def post(self):
        template_values = {}
        username = self.request.get("username")
        password = self.request.get("password")
        if not username:
            template_values['error'] = "Error: Please enter a username"
        usernames = db.GqlQuery(
            ' select *  from Users where username = :1 ', username)
        try:
            user = usernames[0]
            if not hashed_key(
                    password, user.salt).split("|")[0] == user.password_hash:
                template_values['error'] = "Invalid Password"
                template_values['username'] = username
        except:
            template_values['error'] = "Error: Invalid Username"

        if template_values:
            template = jinja_environment.get_template('login.html')
            self.response.out.write(template.render(template_values))
        else:
            user_id = str(user.key().id())
            print user_id
            user_cookie_str = gen_user_cookie(user_id)
            self.response.headers.add_header(
                'Set-Cookie', 'userid = %s; Path=/' % user_cookie_str)

            self.redirect('user/welcome')


class AuthenticationSuccessHandler(webapp2.RequestHandler):

    def get(self):
        self.response.headers['Content-Type'] = 'text/html'
        user_cookie = self.request.cookies.get('userid')
        if user_cookie:
            user = validate_user_cookie(user_cookie)
        else:
            user = None
        if user:
            name = user.username
            template_values = {"name": name}
            template = jinja_environment.get_template(
                'authenticationSuccess.html')
            self.response.out.write(template.render(template_values))
        else:
            self.redirect("/signup")


class LogoutHandler(webapp2.RequestHandler):

    def get(self):
        self.response.delete_cookie('userid')
        self.redirect("/signup")


class BlogHandler(webapp2.RequestHandler):

    def get(self):
        self.response.headers['Content-Type'] = 'text/html'
        q = BlogPost_db.all()
        q.order('-date_created')
        template_values = {"data": q}
        template = jinja_environment.get_template('blog.html')
        self.response.out.write(template.render(template_values))


class BlogNewPostHandler(webapp2.RequestHandler):

    def get(self):
        user_cookie = self.request.cookies.get('userid')
        if user_cookie:
            user = validate_user_cookie(user_cookie)
        if user:
            template_values = {}
            template = jinja_environment.get_template('newpost.html')
            self.response.out.write(template.render(template_values))
        else:
            self.redirect('/login')

    def post(self):
        user_cookie = self.request.cookies.get('userid')
        if user_cookie:
            user = validate_user_cookie(user_cookie)
        if user:
            template_values = {}
            subject = self.request.get("subject")
            content = self.request.get("content")
            # Handles errors messages
            if not subject and not content:
                template_values['error'] = "Error: Enter a blog post"
            elif not content:
                template_values['error'] = "Error: Enter some content"
                template_values['subject'] = subject
            elif not subject:
                template_values['error'] = "Error: Enter a subject"
                template_values["content"] = content

            if template_values:
                template = jinja_environment.get_template('newpost.html')
                self.response.out.write(template.render(template_values))
            else:
                post = BlogPost_db(subject=subject, content=content,
                                   created_by=user.username)
                post_id = post.put().id()
                # print key.id()
                self.redirect('/blog/' + str(post_id))
        else:
            self.redirect('/login')


class PostHandler(webapp2.RequestHandler):

    def get(self, id):
        id = int(id)
        post = BlogPost_db.get_by_id(id)
        comment_data = Comment_db.all()
        comment_data.filter("post_id =", str(id))

        template_values = {"data": post, "comment_data": comment_data}
        template = jinja_environment.get_template('blogpost.html')
        self.response.out.write(template.render(template_values))

    def post(self, id):
        user_cookie = self.request.cookies.get('userid')
        if user_cookie:
            user = validate_user_cookie(user_cookie)
        else:
            user = None
        if user:
            id = int(id)
            template_values = {}
            comment_data = self.request.get("comment")
            # Handles errors messages

            if not comment_data:
                template_values['error'] = "Error: You need to write something"

            if template_values:
                template = jinja_environment.get_template('blogpost.html')
                self.response.out.write(template.render(template_values))
            else:
                new_comment = Comment_db(post_id=str(
                    id), created_by=user.username, text=comment_data)
                new_comment.put()
                # print key.id()
                self.redirect('/blog/' + str(id))
        else:
            self.redirect('/signup')


class EditHandler(webapp2.RequestHandler):

    def get(self, id):
        user_cookie = self.request.cookies.get('userid')
        if user_cookie:
            user = validate_user_cookie(user_cookie)
        else:
            user = None
        if user:
            id = int(id)
            post = BlogPost_db.get_by_id(id)
            if post and post.created_by == user.username:
                template_values = {"data": post}
                template = jinja_environment.get_template('editpost.html')
                self.response.out.write(template.render(template_values))
            else:
                self.response.out.write(
                    "Error: You can't edit someone else's post")
        else:
            self.redirect("/signup")

    def post(self, id):
        user_cookie = self.request.cookies.get('userid')
        if user_cookie:
            user = validate_user_cookie(user_cookie)
        else:
            user = None
        if user:
            id = int(id)
            post = BlogPost_db.get_by_id(id)
            if post:
                template_values = {}
                subject = self.request.get("subject")
                content = self.request.get("content")
                # Handles errors messages
                if not subject and not content:
                    template_values['error'] = "Error: Enter a blog post"
                elif not content:
                    template_values['error'] = "Error: Enter some content"
                    template_values['subject'] = subject
                elif not subject:
                    template_values['error'] = "Error: Enter a subject"
                    template_values['content'] = content

                if template_values:
                    template = jinja_environment.get_template('newpost.html')
                    self.response.out.write(template.render(template_values))
                else:
                    if post.created_by == user.username:
                        post.subject = subject
                        post.content = content
                        post.put()
                        self.redirect('/blog/' + str(id))
        else:
            self.redirect('/signup')


class DeleteHandler(webapp2.RequestHandler):

    def get(self, id):
        user_cookie = self.request.cookies.get('userid')
        if user_cookie:
            user = validate_user_cookie(user_cookie)
        else:
            user = None
        if user:
            id = int(id)
            post = BlogPost_db.get_by_id(id)
            if post and post.created_by == user.username:
                post.delete()
                self.redirect('/blog')
            else:
                self.response.write(
                	"Error: You can't delete someone else's post")


class LikeHandler(webapp2.RequestHandler):

    def get(self, id):
        user_cookie = self.request.cookies.get('userid')
        if user_cookie:
            user = validate_user_cookie(user_cookie)
        else:
            user = None
        if user:
            id = int(id)
            post = BlogPost_db.get_by_id(id)
            if post and not post.created_by == user.username:
                if user.username not in post.liked_by:
                    post.liked_by.append(user.username)
                post.put()
                self.redirect('/blog/' + str(id))
            else:
                self.response.write("Error: You can't like your own post")


class DislikeHandler(webapp2.RequestHandler):

    def get(self, id):
        user_cookie = self.request.cookies.get('userid')
        if user_cookie:
            user = validate_user_cookie(user_cookie)
        else:
            user = None
        if user:
            id = int(id)
            post = BlogPost_db.get_by_id(id)
            if post and not post.created_by == user.username:
                if user.username not in post.disliked_by:
                    post.disliked_by.append(user.username)
                    post.put()
                self.redirect('/blog/' + str(id))
            else:
                self.response.write("Error: You can't dislike your own post")


class EditCommentHandler(webapp2.RequestHandler):

    def get(self, id):
        user_cookie = self.request.cookies.get('userid')
        if user_cookie:
            user = validate_user_cookie(user_cookie)
        else:
            user = None
        if user:
            id = int(id)
            comment = Comment_db.get_by_id(id)
            if comment and comment.created_by == user.username:
                template_values = {"data": comment}
                template = jinja_environment.get_template('editcomment.html')
                self.response.out.write(template.render(template_values))
            else:
                self.response.out.write(
                    "You can't edit someone else's post")
        else:
            self.redirect("/signup")

    def post(self, id):
        user_cookie = self.request.cookies.get('userid')
        if user_cookie:
            user = validate_user_cookie(user_cookie)
        else:
            user = None
        if user:
            id = int(id)
            comment = Comment_db.get_by_id(id)
            if comment and comment.created_by == user.username:
                template_values = {}
                comment_text = self.request.get("comment")
                # Handles errors messages
                if not comment_text:
                    template_values['error'] = "Write Something"

                if template_values:
                    template = jinja_environment.get_template(
                        'editcomment.html')
                    self.response.out.write(template.render(template_values))
                else:
                    comment.text = comment_text
                    comment.put()
                    self.redirect('/blog/' + str(comment.post_id))
        else:
            self.redirect("/signup")


class DeleteCommentHandler(webapp2.RequestHandler):

    def get(self, id):
        user_cookie = self.request.cookies.get('userid')
        if user_cookie:
            user = validate_user_cookie(user_cookie)
        else:
            user = None
        if user:
            id = int(id)
            comment = Comment_db.get_by_id(id)
            if comment and comment.created_by == user.username:
                post_id = comment.post_id
                comment.delete()
                self.redirect('/blog/' + str(post_id))
            else:
                self.response.write("You cannot delete someone else's comment")

app = webapp2.WSGIApplication(
    [('/signup', AuthenticatorHandler),
     ('/user/welcome', AuthenticationSuccessHandler),
        ('/blog', BlogHandler), 
        ('/blog/newpost', BlogNewPostHandler),
        (r'/blog/(\d+)', PostHandler), 
        ('/login', LoginHandler),
        ('/logout', LogoutHandler), 
        (r'/blog/(\d+)/edit', EditHandler),
        (r'/blog/(\d+)/delete', DeleteHandler), 
        (r'/blog/(\d+)/like', LikeHandler),
        (r'/blog/(\d+)/dislike', DislikeHandler),
        (r'/blog/comment/(\d+)/edit', EditCommentHandler),
        (r'/blog/comment/(\d+)/delete', DeleteCommentHandler),
        ('/', BlogHandler),
     ], debug=True)
