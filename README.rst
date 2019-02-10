cfg : git based config files manager and installer
==================================================

This command line tool helps you to keep your customized system configuration files in a
git repository.

Installation
------------

In addition of python3 and related modules, cfg depends of these binaries:

- git
- colordiff

Latest release could be installed via::

  pip3 install cfg-manager
  
Or frome these sources::

  sudo setup.py install

Quickstart
----------

A *cfg* based project is basically composed of:

- a *git* repository with a ``src`` directory where your customized configuration files
  are located, for example::

    src/etc/aliases
    src/etc/apache2/ports.conf
    ...

- a ``cfg_params.py`` file with at least the *TARGET* parameter set, for example::

    TARGET = "/"

Once *TARGET* parameter is configured, you can add existing config file with::

  cfg add /etc/postfix/main.cf

The previous command will create ``src/etc/postfix/main.cf`` file and commit it to the
repository. Don't forget to ``git push`` your work.

To see if your ``src`` and target directory differs, do a::

  cfg check

It will compare the two directories and eventually output differences::

  checking content...
  /etc/aliases :
  2a3
  > root:        f@idez.net

And then::

  cfg install

Will install the modified files, producing the same output. Original dest files are
backed up with ``.old`` extension.

Template files
--------------

For multiple environments usage (duplicated servers, sub-configurations), a pattern
substitution system is provided:

For example let's say you have in your ``cfg_params.py``:

.. code-block:: python

  import socket
  import sys
  HOSTNAME = socket.gethostname()
  if HOSTNAME == "master-kf":
      TARGET = "/"
      HOST_IP = "5.223.34.110"
      PEER_IP = "5.68.252.23"
  elif HOSTNAME == "backup-kf":
      TARGET = "/"
      HOST_IP = "5.68.252.23"
      PEER_IP = "5.223.34.110"
  elif HOSTNAME == "bic":
      TARGET = "/home/fredz/tmp/dst_cfg"
      HOST_IP = "127.0.0.1"
      PEER_IP = "666.666.666.666"
  else:
      print("cfg_params.py : uknown host :", HOSTNAME)
      sys.exit(0)

If you want to use these parameters in one of your config files, let's say ``/etc/keepalived/keepalived.conf``:

1. add it to your repo with ``cfg add``,
2. rename it to ``/etc/keepalived/cfg.keepalived.conf``
3. use ``cfg[PATTERN]`` in your file:

   .. code-block:: squid

    vrrp_instance VI_1 {
        state BACKUP
        interface ens3
        unicast_src_ip =cfg[HOST_IP]
        unicast_peer {
            =cfg[PEER_IP]
        }
    
        virtual_router_id 101
        priority 101
        advert_int 4
        nopreempt
        virtual_ipaddress {
            666.999.999.666
        }
        notify /usr/local/bin/ovh_ip_up.py
    }

Notes:

- As shown in previous example, you can use python code to face various environment
  configurations.
- **Only uppercase parameters names are exported**.

Per-host files
--------------

When configuration files are too different, you can provide host-dedicated versions of
config files : simply prefix desired filenames with "cfg-[HOSTNAME]." where [HOSTNAME] is
the target *hostname*. For example:

   src/etc/cfg-bic.aliases


Permissions
-----------

Because git repositories only handle executable flag permissions,target files
permissions are preserved. It is the more simple and safe approach because most of the
times, target files already exists.

In a future release, I could had *in repository* permission management, but I have no
simple approach yet.


Internals
---------

For safety and fast processing, src and target directories files contents are compared
using git hashes:
  - pre-computed src git sha1 hashes for src
  - ``git hash-object --stdin-paths`` for src, in one system call.
