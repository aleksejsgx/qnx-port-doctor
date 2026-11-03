#!/bin/sh
cd /tmp/qpd && tar xzf cjson-tests.tgz
pass=0; fail=0
for t in cjson_add compare_tests minify_tests misc_tests parse_array parse_examples parse_hex4 parse_number parse_object parse_string parse_value parse_with_opts print_array print_number print_object print_string print_value readme_examples; do
  if ./$t > $t.log 2>&1; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL $t"; tail -3 $t.log; fi
  tail -1 $t.log | sed "s/^/$t: /"
done
echo "suites passed: $pass failed: $fail"
