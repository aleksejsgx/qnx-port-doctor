#!/bin/sh
cd /tmp/qpd; chmod +x uv_run_tests_a
pass=0; fail=0
for t in platform_output hrtime timer timer_again loop_alive loop_stop idle_starvation async thread_create threadpool_queue_work_simple tcp_ping_pong tcp_bind_error_addrinuse_listen udp_send_and_recv pipe_ping_pong fs_file_noent fs_file_async fs_mkdtemp fs_scandir_empty_dir fs_event_watch_file get_loadavg get_memory uname process_title spawn_exit_code signal_multiple_loops getaddrinfo_basic; do
  if ./uv_run_tests_a $t > out.txt 2>&1; then pass=$((pass+1)); r=ok; else fail=$((fail+1)); r=FAIL; fi
  echo "$r $t $(grep -m1 -E 'not ok|Assertion|# SKIP' out.txt)"
done
./uv_run_tests_a platform_output 2>&1 | grep -E "uv_uptime|model|uv_os_uname|sysname" | head -4
echo "passed $pass failed $fail"
