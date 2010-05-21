Data administration
===================

All of the websites data-models can be edited through the administration
site `/timeplan/admin`. However in most cases the admin pages won't be
used at all.

Data manipulation is mainly done through the ``./manage.py`` command.
This script gives access to a host of Django management commands (see
``./manage.py help``.

Creating new super-users
------------------------

::

    > /manage.py createsuperuser
    Username (Leave blank to use 'adamcik'):
    E-mail address: adamcik@stud.ntnu.no
    Password:
    Password (again):
    Superuser created successfully.

Loading courses
---------------

::

   > ./manage.py courses -w
   [2009-08-11 15:19:04 INFO] Updating courses for fall 2009
   [2009-08-11 15:19:04 INFO] Retrieving
   http://www.ntnu.no/studieinformasjon/timeplan/h09/?bokst=A
   [2009-08-11 15:19:05 INFO] Retrieving
   http://www.ntnu.no/studieinformasjon/timeplan/h09/?bokst=B
   ...
   [2009-08-11 15:19:32 INFO] Saved course ZO2051
   [2009-08-11 15:19:32 INFO] Saved course ZO3020
   Save changes? [y/N] y
   Saving changes...

-w tells the script to scrape the NTNU web page, if a the MySQL database with
NTNU courses is available and setup omitting -w means it will be used instead.
All management commands take the option --help.

Loading lectures
----------------

::

    > ./manage.py lectures -w
    [2009-08-11 15:20:24 INFO] Updating lectures for fall 2009
    [2009-08-11 15:20:24 INFO] Retrieving
    http://www.ntnu.no/studieinformasjon/timeplan/h09/?emnekode=AAR1050-1
    [2009-08-11 15:20:24 INFO] Retrieving
    http://www.ntnu.no/studieinformasjon/timeplan/h09/?emnekode=AAR4205-1
    ...
    [2009-08-11 15:21:10 INFO] Saved   87 ZO2051-1 - fall 2009 14:15-17:00 on Fri
    [2009-08-11 15:21:10 INFO] Saved   88 ZO3020-1 - fall 2009 09:15-12:00 on Mon
    Save changes? [y/N] y
    Saving changes...


Running lectures -w, ie. web-retrieval normally takes 5-6 min, to save
time use the -m option to limit which courses to import.

Loading exams
-------------

::

    > ./manage.py exams
    [2009-08-13 14:15:28 INFO] Updating exams for fall 2009
    [2009-08-13 14:15:28 INFO] Getting url:
    http://www.ntnu.no/eksamen/plan/09h/dato.XML
    [2009-08-13 14:15:35 WARNING] ENG2153's exam does not have a date.
    [2009-08-13 14:15:40 WARNING] MV1000's exam is in the past - 2009-05-08
    [2009-08-13 14:15:52 INFO] Added 1051 exams
    [2009-08-13 14:15:52 INFO] Updated 0 exams
    Save changes? [y/N] y
    Saving changes...

Flushing the cache realms
-------------------------

::

    > ./manage.py flushrealms
    [2010-05-22 01:21:15 INFO] Flushing cache for fall 2009

Clear cache for all users connected to a semester.
