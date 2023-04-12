import setuptools

with open("VERSION", "r") as f:
    version = f.read().strip()

with open("README.md", "r") as f:
    long_description = f.read()

setuptools.setup(
   name="cockpitdecks",
   version=version,
   description="Application to use streamdeck, loupedeck, and xtouch-mini with X-Plane flight simulator.",
   author="Pierre M",
   author_email="pierre@devleaks.be",
   url="https://github.com/devleaks/cockpitdecks",
   package_dir={"": "cockpitdecks"},
   packages=setuptools.find_packages(where="cockpitdecks"),
   install_requires=[
      "pillow>=9.5.0",
      "ruamel.yaml"
   ],
   license="MIT",
   long_description=long_description,
   long_description_content_type="text/markdown",
   include_package_data=True,
   python_requires=">=3.8,<3.11",
)
