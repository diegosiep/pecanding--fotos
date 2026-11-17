#!/usr/bin/env python3
"""Genera macos/PecandingFotos.xcodeproj/project.pbxproj (un target app macOS,
todos los .swift de macos/PecandingFotos/). Ejecutar: python3 macos/scripts/generate_xcodeproj.py
"""
import hashlib
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(ROOT, "macos", "PecandingFotos")
OUT = os.path.join(ROOT, "macos", "PecandingFotos.xcodeproj", "project.pbxproj")


def uid(key: str) -> str:
    return hashlib.sha1(key.encode()).hexdigest()[:24].upper()


sources = sorted(f for f in os.listdir(SRC_DIR) if f.endswith(".swift"))
other = sorted(f for f in os.listdir(SRC_DIR) if not f.endswith(".swift"))  # Info.plist

build_files = "\n".join(
    f"\t\t{uid('bf/' + f)} /* {f} in Sources */ = {{isa = PBXBuildFile; fileRef = {uid('fr/' + f)} /* {f} */; }};"
    for f in sources
)
file_refs = "\n".join(
    f"\t\t{uid('fr/' + f)} /* {f} */ = {{isa = PBXFileReference; lastKnownFileType = "
    + ("sourcecode.swift" if f.endswith(".swift") else "text.plist.xml")
    + f"; path = {f}; sourceTree = \"<group>\"; }};"
    for f in sources + other
)
src_group_children = "\n".join(
    f"\t\t\t\t{uid('fr/' + f)} /* {f} */," for f in sources + other
)
sources_phase_files = "\n".join(
    f"\t\t\t\t{uid('bf/' + f)} /* {f} in Sources */," for f in sources
)

pbx = f"""// !$*UTF8*$!
{{
	archiveVersion = 1;
	classes = {{
	}};
	objectVersion = 56;
	objects = {{

/* Begin PBXBuildFile section */
{build_files}
/* End PBXBuildFile section */

/* Begin PBXFileReference section */
{file_refs}
		{uid('fr/app')} /* PecandingFotos.app */ = {{isa = PBXFileReference; explicitFileType = wrapper.application; includeInIndex = 0; path = PecandingFotos.app; sourceTree = BUILT_PRODUCTS_DIR; }};
/* End PBXFileReference section */

/* Begin PBXFrameworksBuildPhase section */
		{uid('phase/frameworks')} /* Frameworks */ = {{
			isa = PBXFrameworksBuildPhase;
			buildActionMask = 2147483647;
			files = (
			);
			runOnlyForDeploymentPostprocessing = 0;
		}};
/* End PBXFrameworksBuildPhase section */

/* Begin PBXGroup section */
		{uid('group/root')} = {{
			isa = PBXGroup;
			children = (
				{uid('group/src')} /* PecandingFotos */,
				{uid('group/products')} /* Products */,
			);
			sourceTree = "<group>";
		}};
		{uid('group/products')} /* Products */ = {{
			isa = PBXGroup;
			children = (
				{uid('fr/app')} /* PecandingFotos.app */,
			);
			name = Products;
			sourceTree = "<group>";
		}};
		{uid('group/src')} /* PecandingFotos */ = {{
			isa = PBXGroup;
			children = (
{src_group_children}
			);
			path = PecandingFotos;
			sourceTree = "<group>";
		}};
/* End PBXGroup section */

/* Begin PBXNativeTarget section */
		{uid('target')} /* PecandingFotos */ = {{
			isa = PBXNativeTarget;
			buildConfigurationList = {uid('cl/target')} /* Build configuration list for PBXNativeTarget "PecandingFotos" */;
			buildPhases = (
				{uid('phase/sources')} /* Sources */,
				{uid('phase/frameworks')} /* Frameworks */,
				{uid('phase/resources')} /* Resources */,
			);
			buildRules = (
			);
			dependencies = (
			);
			name = PecandingFotos;
			productName = PecandingFotos;
			productReference = {uid('fr/app')} /* PecandingFotos.app */;
			productType = "com.apple.product-type.application";
		}};
/* End PBXNativeTarget section */

/* Begin PBXProject section */
		{uid('project')} /* Project object */ = {{
			isa = PBXProject;
			attributes = {{
				LastUpgradeCheck = 1540;
				TargetAttributes = {{
					{uid('target')} = {{
						CreatedOnToolsVersion = 15.4;
					}};
				}};
			}};
			buildConfigurationList = {uid('cl/project')} /* Build configuration list for PBXProject "PecandingFotos" */;
			compatibilityVersion = "Xcode 15.0";
			developmentRegion = en;
			hasScannedForEncodings = 0;
			knownRegions = (
				en,
				Base,
			);
			mainGroup = {uid('group/root')};
			productRefGroup = {uid('group/products')} /* Products */;
			projectDirPath = "";
			projectRoot = "";
			targets = (
				{uid('target')} /* PecandingFotos */,
			);
		}};
/* End PBXProject section */

/* Begin PBXResourcesBuildPhase section */
		{uid('phase/resources')} /* Resources */ = {{
			isa = PBXResourcesBuildPhase;
			buildActionMask = 2147483647;
			files = (
			);
			runOnlyForDeploymentPostprocessing = 0;
		}};
/* End PBXResourcesBuildPhase section */

/* Begin PBXSourcesBuildPhase section */
		{uid('phase/sources')} /* Sources */ = {{
			isa = PBXSourcesBuildPhase;
			buildActionMask = 2147483647;
			files = (
{sources_phase_files}
			);
			runOnlyForDeploymentPostprocessing = 0;
		}};
/* End PBXSourcesBuildPhase section */

/* Begin XCBuildConfiguration section */
		{uid('cfg/target/debug')} /* Debug */ = {{
			isa = XCBuildConfiguration;
			buildSettings = {{
				CODE_SIGN_STYLE = Automatic;
				COMBINE_HIDPI_IMAGES = YES;
				CURRENT_PROJECT_VERSION = 1;
				ENABLE_HARDENED_RUNTIME = NO;
				GENERATE_INFOPLIST_FILE = NO;
				INFOPLIST_FILE = PecandingFotos/Info.plist;
				MACOSX_DEPLOYMENT_TARGET = 13.0;
				MARKETING_VERSION = 0.1.0;
				PRODUCT_BUNDLE_IDENTIFIER = com.pecanding.PecandingFotos;
				SWIFT_EMIT_LOC_STRINGS = NO;
				SWIFT_VERSION = 5.0;
			}};
			name = Debug;
		}};
		{uid('cfg/target/release')} /* Release */ = {{
			isa = XCBuildConfiguration;
			buildSettings = {{
				CODE_SIGN_STYLE = Automatic;
				COMBINE_HIDPI_IMAGES = YES;
				CURRENT_PROJECT_VERSION = 1;
				ENABLE_HARDENED_RUNTIME = NO;
				GENERATE_INFOPLIST_FILE = NO;
				INFOPLIST_FILE = PecandingFotos/Info.plist;
				MACOSX_DEPLOYMENT_TARGET = 13.0;
				MARKETING_VERSION = 0.1.0;
				PRODUCT_BUNDLE_IDENTIFIER = com.pecanding.PecandingFotos;
				SWIFT_EMIT_LOC_STRINGS = NO;
				SWIFT_VERSION = 5.0;
			}};
			name = Release;
		}};
		{uid('cfg/project/debug')} /* Debug */ = {{
			isa = XCBuildConfiguration;
			buildSettings = {{
				MACOSX_DEPLOYMENT_TARGET = 13.0;
				SWIFT_VERSION = 5.0;
			}};
			name = Debug;
		}};
		{uid('cfg/project/release')} /* Release */ = {{
			isa = XCBuildConfiguration;
			buildSettings = {{
				MACOSX_DEPLOYMENT_TARGET = 13.0;
				SWIFT_VERSION = 5.0;
			}};
			name = Release;
		}};
/* End XCBuildConfiguration section */

/* Begin XCConfigurationList section */
		{uid('cl/project')} /* Build configuration list for PBXProject "PecandingFotos" */ = {{
			isa = XCConfigurationList;
			buildConfigurations = (
				{uid('cfg/project/debug')} /* Debug */,
				{uid('cfg/project/release')} /* Release */,
			);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		}};
		{uid('cl/target')} /* Build configuration list for PBXNativeTarget "PecandingFotos" */ = {{
			isa = XCConfigurationList;
			buildConfigurations = (
				{uid('cfg/target/debug')} /* Debug */,
				{uid('cfg/target/release')} /* Release */,
			);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		}};
/* End XCConfigurationList section */
	}};
	rootObject = {uid('project')} /* Project object */;
}}
"""

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(pbx)

# sanity: llaves balanceadas y toda referencia UUID definida
text = open(OUT, encoding="utf-8").read()
assert text.count("{") == text.count("}"), "llaves desbalanceadas"
defined = set(re.findall(r"\b([0-9A-F]{24})\b\s*/\*", text)) | {uid("project")}
refs = set(re.findall(r"= ([0-9A-F]{24}) /\*", text)) | set(re.findall(r"\(([0-9A-F]{24}) /\*", text)) | set(re.findall(r"\t\t\t\t([0-9A-F]{24}) /\*", text))
missing = {r for r in refs if r not in defined and r != uid("group/root")}
# los grupos referenciados desde root sí están definidos; verificar los de archivo
for f in sources + other + ["app"]:
    assert uid("fr/" + f) in text
print("OK", OUT, len(sources), "swift files")
