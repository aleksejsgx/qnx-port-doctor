/* qnx_compat.h - force-included shims for common Linux/BSD assumptions on QNX 8.
 * Use with: CFLAGS += -include qnx_compat.h
 * SPDX-License-Identifier: MIT
 */
#ifndef QNX_COMPAT_H
#define QNX_COMPAT_H
#ifdef __QNX__
#include <limits.h>
#include <signal.h>
#include <sys/uio.h>
/* QNX <limits.h> leaves IOV_MAX undefined (runtime value: sysconf(_SC_IOV_MAX)). */
#ifndef IOV_MAX
#define IOV_MAX UIO_MAXIOV
#endif
/* SA_RESTART is "not supported yet" on QNX 8: callers must already handle EINTR. */
#ifndef SA_RESTART
#define SA_RESTART 0
#endif
#endif
#endif
