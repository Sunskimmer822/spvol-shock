import msvcrt,sys,pyaudio,time
from math import log10
#ts deprecated as of python 3.13!!!!!!!!!! pip install audioop-lts !!!!!!!!!!!!
import audioop
#ts not built in!!!!!!!!!!! pip install pishock !!!!!!!!!!!!
from pishock import PiShockAPI
import environment as env

def send_help():
    print(f"Incorrect usage. See {env.helptext_color}python ./volshocker.py --help{env.reset_color} for help.")

def send_help_and_abort():
    print(f"Incorrect usage. See {env.helptext_color}python ./volshocker.py --help{env.reset_color} for help. Exiting.")
    sys.exit(1)

def print_help():
    print(
        f"Usage: python ./volshocker.py [OPTION]...\n\n"
        
        f"Options:\n\n"
        
        f"   {env.helptext_color}-s, --enable_shock{env.reset_color}\n"
        f"      Toggle whether the shocker should shock or vibrate when triggered.\n"
        f"      Options: Boolean (True, False, T, F)\n"
        f"      Example: -s True\n\n"
        
        f"   {env.helptext_color}-w, --wait-while-shocking{env.reset_color}\n"
        f"      Toggle whether the shocker should be sent commands while a shock is already being performed.\n"
        f"      Options: Boolean (True, False, T, F)\n"
        f"      Example: -w F\n\n"
        
        f"   {env.helptext_color}-p, --power{env.reset_color}\n"
        f"      Choose the power of the shock/vibration.\n"
        f"      If the shocker has limits, they will override this option if it is too high.\n"
        f"      Options: Integer [0,100]\n"
        f"      Example: -p 69\n\n"
        
        f"   {env.helptext_color}-d, --duration{env.reset_color}\n"
        f"      Choose the duration of the shock/vibration.\n"
        f"      If the shocker has limits, they will override this option if it is too high.\n"
        f"      Options: Float [0,15]\n"
        f"      Example: -d 2.1\n\n"
        
        f"   {env.helptext_color}--help{env.reset_color}  Display this help and exit."
    )



#args

for i in range(len(sys.argv)):
    arg = sys.argv[i]
    if arg == "--help":
        print_help()
        sys.exit()
    if len(sys.argv)>i+1:
        next_arg = sys.argv[i+1]
    else:
        break
    if arg == "-s" or arg == "--enable-shock":
        if next_arg.capitalize() == "True" or next_arg.capitalize() == "False":
            env.shock_enabled = bool(next_arg)
        elif next_arg.capitalize() == "T":
            env.shock_enabled = True
        elif next_arg.capitalize() == "F":
            env.shock_enabled = False
        else:
            print("Incorrectly formatted boolean. No values have been changed.")
            send_help()
    elif arg == "-w" or arg == "--wait-while-shocking":
        if next_arg.capitalize() == "True" or next_arg.capitalize() == "False":
            env.disable_on_trigger = bool(next_arg)
        elif next_arg.capitalize() == "T":
            env.disable_on_trigger = True
        elif next_arg.capitalize() == "F":
            env.disable_on_trigger = False
        else:
            print("Incorrectly formatted boolean. No values have been changed.")
            send_help()
    elif arg == "-p" or arg == "--power":
        power = int(next_arg)
        if power<0: power = 0
        if power>100: power = 1000
        env.trigger_power = power
    elif arg == "-d" or arg == "--duration":
        duration = float(next_arg)
        if duration<0: duration = 0
        if duration>15: duration = 15
        env.trigger_duration = duration

#sanitiziation
needs_help = False
if env.username == "":
    print("No username present in environment.py.")
    needs_help = True
if env.api_key == "":
    print("No pishock API key present in environment.py.")
    needs_help = True
if env.share_code == "":
    print("No pishock share code present in environment.py.")
    needs_help = True

if needs_help:
    send_help_and_abort()

#deal with possibility of putting a link in the share code section
try:
    if env.share_code.index("=")!=-1:
        env.share_code = env.share_code[ env.share_code.index("=")+1 : len(env.share_code)-1 ]
except ValueError:
    pass #this means there was no = present, which means there was a real code and not a link. we do not have to handle this.

#initialize shocker

api = PiShockAPI(env.username,env.api_key)
shocker = api.shocker(env.share_code)

shocker_info = shocker.info()
shocker_max_intensity = shocker_info.max_intensity
shocker_max_duration = shocker_info.max_duration
shocker.beep(.5)

p = pyaudio.PyAudio()
WIDTH = 2
RATE = int(p.get_default_input_device_info()['defaultSampleRate'])
DEVICE = p.get_default_input_device_info()['index']
rms = 1
print(p.get_default_input_device_info())

def callback(in_data, frame_count, time_info, status):
    global rms
    rms = audioop.rms(in_data, WIDTH) / 32767
    return in_data, pyaudio.paContinue


stream = p.open(format=p.get_format_from_width(WIDTH),
                input_device_index=DEVICE,
                channels=1,
                rate=RATE,
                input=True,
                output=False,
                stream_callback=callback)

stream.start_stream()


calibration_steps = 20
thrown_steps = 4
cur_calibration_step = 0

calibration_data = []

baseline = -40
threshold = 35

measurement_delay = 0.3

while stream.is_active():
    #abort the loop by holding the break key (ESC by default)
    if msvcrt.kbhit() and msvcrt.getch()[0] == 27:
        #loop broke! I'm out of here!
        print("Keyboard interrupt caught. Exiting shocker loop.")
        break
    if not rms<sys.float_info.min:
        db = 20 * log10(rms)
    else:
        db = baseline
    if (cur_calibration_step!=-1) and (cur_calibration_step>=calibration_steps+thrown_steps):
        #finish
        for i in range(thrown_steps):
            calibration_data.pop(0)
        cur_calibration_step = -1
        data_sum = 0
        for value in calibration_data:
            data_sum += value
        baseline = data_sum/len(calibration_data)
    elif (cur_calibration_step!=-1) and (cur_calibration_step<=calibration_steps+thrown_steps):
        calibration_data.append(db)
        print(f"Calibration point {cur_calibration_step}: {db}db")
        cur_calibration_step+=1
    else:
        #check for shock
        if db-baseline>threshold:
            #we shock here
            print(f"{"SHOCKING" if env.shock_enabled else "VIBRATING"} at {env.trigger_power}% power for {env.trigger_duration}s due to {db-baseline-threshold:2.2f} over threshold.")

            if env.shock_enabled:
                shocker.shock(intensity=env.trigger_power,duration=env.trigger_duration)
            else:
                shocker.vibrate(intensity=env.trigger_power,duration=env.trigger_duration)
    # refresh every 0.3 seconds
    time.sleep(measurement_delay)

stream.stop_stream()
stream.close()

p.terminate()

shocker.beep(.5)













#hello to you who're present with me here at the end of this earth.
#this program was made with love and care (twice! oops) for my friend julie because she's a weird freak <3
#issues, feedback, PRs, and whatnot are very much accepted. but i dont really care if you make one or not.
#you have free will, reader, do whatever you want forever!


#reach heaven through incredible violence, girl.