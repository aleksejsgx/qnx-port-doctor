#!/bin/sh
cd /tmp/qpd; chmod +x tmux
export TERM=xterm
./tmux -V
./tmux -S /tmp/qpd/sock -f /dev/null new-session -d -s qnx -x 80 -y 24 'echo hello-from-tmux-on-qnx; uname -sr; sleep 30' ; echo new=$?
sleep 2
./tmux -S /tmp/qpd/sock ls
./tmux -S /tmp/qpd/sock capture-pane -p -t qnx | grep -v '^$'
./tmux -S /tmp/qpd/sock split-window -t qnx 'sleep 30'; ./tmux -S /tmp/qpd/sock list-panes -t qnx
./tmux -S /tmp/qpd/sock kill-server; echo kill=$?
