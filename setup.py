from distutils.core import setup

setup(name = 'synergy_scheduler',
      version = '1.2',
      description = 'Synergy Scheduler',
      author = 'Bohdan Mushkevych',
      author_email = 'mushkevych@gmail.com',
      url = 'https://github.com/mushkevych/scheduler',
      packages = ['synergy.db', 'synergy.db.dao', 'synergy.db.manager', 'synergy.db.model', 'synergy.mq',
                  'synergy.mx', 'synergy.scheduler', 'synergy.supervisor', 'synergy.system', 'synergy.workers'],
      package_data = {'synergy.mx': ['static/*', 'templates/*'],
                      'synergy.mq': ['AUTHORS', 'LICENSE']},
      long_description = '''Really long text here.''',
      license = 'Modified BSD License',
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Environment :: Web Environment',
          'Intended Audience :: End Users/Desktop',
          'Intended Audience :: Developers',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: BSD License',
          'Operating System :: POSIX',
          'Programming Language :: Python',
          'Programming Language :: JavaScript',
          'Topic :: Communications :: Email',
          'Topic :: Office/Business :: Scheduling',
          'Topic :: Utilities',
          ],
      requires=['werkzeug', 'jinja2', 'amqp', 'pymongo', 'psutil', 'fabric', 'setproctitle']
)