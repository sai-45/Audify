import os
import secrets
from PIL import Image
from flask import render_template, url_for, flash, redirect,send_file,request,current_app
from flaskblog import app,db,bcrypt
from flaskblog.forms import RegistrationForm, LoginForm,VideoToAudioForm,AudioToTextForm, UpdateAccountForm,PostForm,SongForm
from flaskblog.models import User, Post,Song
import moviepy.editor as mp
from flaskblog.caption_generator import save_transcript,upload
from flask_login import login_user, current_user, logout_user, login_required
from werkzeug.utils import secure_filename


# with app.app_context():
#     db.create_all()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))  # Get the base directory


@app.route("/")
@app.route("/home")
def home():
    posts = Post.query.all()
    
    return render_template('home.html', posts=posts)


@app.route("/about")
def about():
    return render_template('about.html', title='About')


@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))


def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_fn)

    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture_fn

@app.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            current_user.image_file = picture_file
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your account has been updated!', 'success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    image_file = url_for('static', filename='profile_pics/' + current_user.image_file)
    return render_template('account.html', title='Account',
                           image_file=image_file, form=form)


@app.route('/convert', methods=['GET','POST'])
def convert():
    form = VideoToAudioForm()
    audio_ready = False  # Flag to indicate if the audio is ready for download

    if form.validate_on_submit():
        video = form.video.data

        # Save video file
        video_filename = video.filename
        video_path = os.path.join(BASE_DIR, 'input_video.mp4')
        video.save(video_path)
        # Convert video to audio
        try:
            audio_filename = os.path.splitext(video_filename)[0] + '.mp3'
            audio_path = os.path.join(BASE_DIR, audio_filename)
            clip = mp.VideoFileClip(video_path)
            clip.audio.write_audiofile(audio_path)
            clip.close()  # Close the clip to release the file
            # Remove the input video file
            os.remove(video_path)
            audio_ready = True  # Set the flag to indicate audio is ready for download
        except Exception as e:
            return f'Error converting video to audio: {str(e)}'

        return render_template('convert.html', form=form, audio_ready=audio_ready,audio_filename=audio_filename)
    
    return render_template('convert.html', form=form,audio_ready=audio_ready)


@app.route('/download_audio/<audio_filename>')
def download_audio(audio_filename):
    audio_path = os.path.join(BASE_DIR, audio_filename)
    return send_file(audio_path, as_attachment=True, download_name=audio_filename)




@app.route('/caption_generator', methods=['GET','POST'])
def caption_generator():
    form = AudioToTextForm()
    text_ready = False  # Flag to indicate if the text is ready for download

    if form.validate_on_submit():
        audio = form.audio.data

        # Save audio file
        audio_filename = audio.filename
        audio_path = os.path.join(BASE_DIR, 'input_audio.mp3')
        audio.save(audio_path)
        
        # Generate  Captions
        
        text_filename = os.path.splitext(audio_filename)[0] +'.txt'
        #text_path = os.path.join(os.getcwd(),'flaskblog/'+ text_filename)
        
        audio_url = upload(audio_path)
        save_transcript(audio_url,text_filename)
        text_ready = True
        print(text_filename)

        return render_template('caption_generator.html', form=form, text_ready=text_ready,text_filename=text_filename)
    
    return render_template('caption_generator.html', form=form,atext_ready=text_ready)




@app.route('/download_captions/<text_filename>')
def download_captions(text_filename):
    text_path = os.path.join(os.getcwd(),'flaskblog/'+ text_filename)
    return send_file(text_path, as_attachment=True, download_name=text_filename)



@app.route("/post/new", methods=['GET', 'POST'])
@login_required
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(title=form.title.data, content=form.content.data, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('Your post has been created!', 'success')
        return redirect(url_for('home'))
    return render_template('create_post.html', title='New Post',
                           form=form, legend='New Post')
    
    

@app.route("/my_playlist", methods=['GET', 'POST'])
@login_required
def my_playlist():
    songs = Song.query.filter_by(user_id=current_user.id).all()
    form = SongForm()
    if form.validate_on_submit():
        audio_file = form.audio_file.data
        audio_filename = secure_filename(audio_file.filename)
        audio_path = os.path.join(current_app.root_path, 'static/audio', audio_filename)
        audio_file.save(audio_path)
        
        captions_file = form.captions_file.data
        captions_filename = secure_filename(captions_file.filename)
        captions_path = os.path.join(current_app.root_path, 'static/captions', captions_filename)
        captions_file.save(captions_path)

        song = Song(title=form.title.data, artist=form.artist.data, audio_path=audio_path, captions_path=captions_path, owner=current_user)
        db.session.add(song)
        db.session.commit()
        flash('Your song has been added!', 'success')
        return redirect(url_for('home'))
    
    captions = {}  # Dictionary to store captions content for each song
    for song in songs:
        print(song.captions_path)
        if song.captions_path:
            captions_path = os.path.join(current_app.root_path, 'static/captions', song.captions_path)
            with open(captions_path, 'r') as captions_file:
                captions_content = captions_file.read()
                captions[song.id] = captions_content
    return render_template('my_playlist.html', title='New Song', form=form, legend='New Song',songs=songs,captions=captions)


# @app.route("/song/audio/<audio_filename>")
# def download_audio(audio_filename):
#     audio_path = os.path.join(current_app.root_path, 'static/audio', audio_filename)
#     return send_file(audio_path, as_attachment=False)