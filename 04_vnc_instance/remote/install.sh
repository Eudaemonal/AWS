#!/bin/sh

# install packages
sudo apt-get -y update
sudo apt-get -y upgrade
sudo apt-get -y install expect
sudo apt-get -y install ubuntu-desktop gnome-panel vnc4server gnome-settings-daemon metacity nautilus gnome-terminal xfce4 

# setup vncserver password
prog=/usr/bin/vncpasswd
mypass="newpass"

/usr/bin/expect <<EOF
spawn "$prog"
expect "Password:"
send "$mypass\r"
expect "Verify:"
send "$mypass\r"
expect eof
exit
EOF

cp -rf xstartup .vnc/
chmod +x ~/.vnc/xstartup

# Add your customised installation commands
