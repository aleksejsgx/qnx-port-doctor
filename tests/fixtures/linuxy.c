#include <sys/epoll.h>
#include <sys/prctl.h>
#include <stdio.h>
int main(void){
    int e = epoll_create1(0);
    prctl(PR_SET_NAME, "x");
    FILE *f = fopen("/proc/self/maps", "r");
    return e + (f != 0);
}
