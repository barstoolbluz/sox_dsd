#####################################
# CMAKE file for the SoX DSD fork #
#                                   #
# Dr. Thomas Tensi, 2026-02         #
#####################################

CMAKE_MINIMUM_REQUIRED(VERSION 4.0)

PROJECT(SoX_DSD
        VERSION 1.0.0
        LANGUAGES C)

# Keep this release baseline in sync with configure.ac on upstream sync.
SET(SOX_DSD_UPSTREAM_BASE "14.8.1")

# =============================
# === program configuration ===
# =============================

INCLUDE(GNUInstallDirs)

# global includes
INCLUDE(_UtilityFunctions.cmake)
INCLUDE(_GlobalConfiguration.cmake)

# --- define the settings for the C compiler ---
INCLUDE(_CCompilerConfiguration.cmake)

# --- define the settings for the linker and librarian ---
INCLUDE(_CLinkerConfiguration.cmake)

# --- define support for automatic configuration (autoconf emulation)
INCLUDE(_AutomaticConfiguration.cmake)

# project specific includes

# --- process the command line parameters ---
INCLUDE(CommandLineParameters.cmake)

# --- do some local configuration ---
INCLUDE(LocalSettings.cmake)

# --- doxygen (for the developer documentation) ---
FIND_PACKAGE(Doxygen)

# ===================
# === directories ===
# ===================

CMAKE_PATH(SET buildSetupDirectory NORMALIZE
           ${CMAKE_CURRENT_SOURCE_DIR})

CMAKE_PATH(SET buildSetupTemplateDirectory NORMALIZE
           ${buildSetupDirectory}/templates)

# --- source directories ---
CMAKE_PATH(SET soxSrcDirectory NORMALIZE
           ${GLOB_projectRootDirectory}/src)

# --- test file directory ---
CMAKE_PATH(SET testFileDirectory NORMALIZE
           ${GLOB_projectRootDirectory}/test)

# --- add dynamic linkage library for MacOS and Unix ---
IF(NOT WINDOWS)
    LINK_LIBRARIES(${CMAKE_DL_LIBS})
ENDIF(NOT WINDOWS)

# --- enable PkgConfig for MacOS and Unix ---
IF(NOT WINDOWS)
    FIND_PACKAGE(PkgConfig) 
ENDIF(NOT WINDOWS)

#############
# FUNCTIONS #
#############

MACRO(_installSymbolicLink symbolicLinkPath filePath)
    # Symlinks are relative, relocatable, and staged under DESTDIR.
    # Report a failed alias install instead of printing a false success.
    GET_FILENAME_COMPONENT(linkTarget "${filePath}" NAME)
    GET_FILENAME_COMPONENT(linkDirectory "${symbolicLinkPath}" DIRECTORY)
    INSTALL(CODE "
        file(MAKE_DIRECTORY \"\$ENV{DESTDIR}${linkDirectory}\")
        file(REMOVE \"\$ENV{DESTDIR}${symbolicLinkPath}\")
        execute_process(
            COMMAND \"${CMAKE_COMMAND}\" -E create_symlink
                    \"${linkTarget}\" \"\$ENV{DESTDIR}${symbolicLinkPath}\"
            RESULT_VARIABLE linkResult)
        if(NOT linkResult EQUAL 0)
            message(FATAL_ERROR \"Cannot install ${symbolicLinkPath} -> ${linkTarget}\")
        endif()
    ")
ENDMACRO(_installSymbolicLink)

#--------------------

MACRO(appendNameConditionally variableName name)
    # checks hasLocalLibXXX for <name> and, if set, adds <name> to
    # variable with name <variableName>

    SET(conditionVariableName "hasLocalLib${name}")

    IF(${conditionVariableName})
        LIST(APPEND ${variableName} ${name})
    ENDIF()
ENDMACRO(appendNameConditionally)

#--------------------

MACRO(installManPage name manChapter)
    # Command pages have canonical filenames; lib/effect pages retain the
    # SoX-NG library documentation names to avoid an ABI/documentation rename.
    IF("${name}" STREQUAL "sox" OR "${name}" STREQUAL "soxi")
        SET(fileName "${name}.${manChapter}")
    ELSE()
        SET(fileName "${name}_ng.${manChapter}")
    ENDIF()
    SET(filePath "${GLOB_projectRootDirectory}/${fileName}")
    SET(directory "${CLP_installManPath}/man${manChapter}")
    INSTALL(FILES ${filePath} DESTINATION ${directory})

    IF("${name}" STREQUAL "sox" OR "${name}" STREQUAL "soxi")
        IF(NOT CLP_disableSymlinks)
            _installSymbolicLink("${directory}/${name}_ng.${manChapter}"
                                 "${directory}/${fileName}")
        ENDIF()
    ELSEIF(CLP_enableReplace)
        _installSymbolicLink("${directory}/${name}.${manChapter}"
                             "${directory}/${fileName}")
    ENDIF()
ENDMACRO(installManPage)

#--------------------

MACRO(installSymbolicLink kind newName oldName)
    # installs symlink from file <newName> to file <oldName> where
    # <kind> gives the kind of file (exe, lib, man)

    IF("${kind}" STREQUAL "exe")
        SET(directory ${CLP_installBinPath}) 
        SET(extension ${LINKER_executableExtension})
    ELSEIF("${kind}" STREQUAL "lib")
        SET(directory ${CLP_installLibPath}) 
        SET(extension ${LINKER_staticLibraryExtension})
    ENDIF()

    SET(symbolicLinkPath "${directory}/${newName}${extension}")
    SET(filePath         "${directory}/${oldName}${extension}")
    _installSymbolicLink(${symbolicLinkPath} ${filePath})
ENDMACRO(installSymbolicLink)

#--------------------

MACRO(makeDoxygenDocumentation)
    # generates doxygen documentation

    CMAKE_PATH(SET doxygenConfigurationFile NORMALIZE
               ${GLOB_projectRootDirectory}/Doxyfile)
    SET(doxygenFileList
        "${soxSrcDirectory}
        ${GLOB_projectRootDirectory}/Doxymain.md")
    DOXYGEN_ADD_DOCS(libSoXDocumentation
                     ${doxygenFileList}
                     ALL
                     WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}
                     COMMENT "Generating API documentation for libSoX"
                     CONFIG_FILE ${doxygenConfigurationFile})
ENDMACRO(makeDoxygenDocumentation)

#--------------------

FUNCTION(processSubtargetConditionally
         targetName parentTargetName languageStandard)
    # includes CMake file for <targetName> when associated library
    # directory is set; <parentTargetName> gives the name of the
    # parent target and <languageStandard> gives the C language
    # standard

    MESSAGE("=== setting up ${targetName} ===")
    STRING(TOLOWER ${targetName} lowercasedTargetName)

    SET(includeFileName "SubTarget_${lowercasedTargetName}.cmake")
    INCLUDE(${includeFileName})
    STRING(SUBSTRING "${targetName}" 3 -1 libraryName)
    UTIL_Target_setFolder(${targetName} ${folderName_supportLibs})
    SET_TARGET_PROPERTIES(${targetName} PROPERTIES
                          C_STANDARD ${languageStandard}
                          C_STANDARD_REQUIRED FALSE)
ENDFUNCTION(processSubtargetConditionally)

###########
# TARGETS #
###########

#----------------
# common settings
#----------------

SET(folderName_examples    "Examples")
SET(folderName_supportLibs "SupportLibs")

# ============================
# === supporting libraries ===
# ============================

SET(supportLibsRootTargetName "SupportLibraries")

ADD_CUSTOM_TARGET(${supportLibsRootTargetName})
UTIL_Target_setFolder(${supportLibsRootTargetName} ${folderName_supportLibs})

# --- process all libraries

SET(libraryShortNameList
    "FFTW" "Flac" "Id3tag" "Mad" "MP3Lame" "Ogg" "Opus" "Opusfile"
    "Png" "Sndfile" "Speex" "SpeexDSP" "Vorbis" "Wavpack" "Z"
)

# --- do consistency checks ---

FOREACH(shortName ${libraryShortNameList})
    SET(configurationVariableName "hasLocalLib${shortName}")
    SET(directoryVariableName "LCONF_lib${shortName}Directory")
    SET(exclusionVariableName "CLP_without${shortName}")
    SET(targetName "lib${shortName}")

    SET(${configurationVariableName} FALSE)
    UTIL_Debug_appendRelevantVariableNames(${configurationVariableName})
    SET(messagePrefix "cannot build ${targetName},")

    IF(${exclusionVariableName})
        MESSAGE(STATUS "${messagePrefix} excluded from build")
    ELSEIF("${${directoryVariableName}}" STRGREATER "")
        SET(${configurationVariableName} TRUE)
    ELSE()
        MESSAGE(STATUS "${messagePrefix} directory not defined")
    ENDIF()
ENDFOREACH()

SET(libFlacUsesOgg TRUE)

# --- traverse the libraries
FOREACH(shortName ${libraryShortNameList})
    SET(configurationVariableName "hasLocalLib${shortName}")

    IF(${configurationVariableName})
        IF("${shortName}" STREQUAL "Mad")
            # Mad is not conforming to C99
            SET(languageStandard 90)
        ELSE()
            SET(languageStandard 99)
        ENDIF()

        processSubtargetConditionally("lib${shortName}"
                                      ${supportLibsRootTargetName}
                                      ${languageStandard})
    ENDIF()
ENDFOREACH()

IF(libFlacUsesOgg AND hasLocalLibFlac)
    ADD_DEPENDENCIES(libFlac libOgg)
ENDIF()

# --- collect active libraries
SET(activeLibraryNameList )

FOREACH(shortName ${libraryShortNameList})
    appendNameConditionally(activeLibraryNameList ${shortName})
ENDFOREACH()

# ======================
# === LibSoX library ===
# ======================

INCLUDE(Target_libsox.cmake)

# ======================
# === SoX executable ===
# ======================

INCLUDE(Target_sox.cmake)

# ====================
# === SoX examples ===
# ====================

INCLUDE(Target_soxExamples.cmake)

# =====================
# DOXYGEN documentation
# =====================

IF(NOT Doxygen_FOUND)
    MESSAGE("Doxygen needs to be installed to generate the documentation")
ELSE()
    makeDoxygenDocumentation()
ENDIF()

################
# INSTALLATION #
################

# === install SoX library ===
INSTALL(TARGETS libSoX DESTINATION ${CLP_installLibPath})

# === install SoX binaries ===
INSTALL(TARGETS SoX DESTINATION ${CLP_installBinPath})
IF(NOT CLP_disableSymlinks)
    # Canonical companions and existing _ng compatibility commands.
    FOREACH(name IN ITEMS soxi play rec soxi_ng play_ng rec_ng)
        installSymbolicLink(exe ${name} sox)
    ENDFOREACH()
ENDIF()

# === install SoX example binaries ===
FOREACH(fileIndex ${soxExampleFileIndexList})
    SET(exampleTargetName "SoXExamples_${fileIndex}")
    INSTALL(TARGETS ${exampleTargetName} DESTINATION ${CLP_installBinPath})
ENDFOREACH()

# === install optional legacy/unversioned library compatibility names ===
IF(CLP_enableReplace)
    installSymbolicLink(lib libsox libsox_ng)
    FOREACH(fileIndex ${soxExampleFileIndexList})
        SET(executableFileName "sox_ng_example${fileIndex}")
        SET(linkFileName       "sox_example${fileIndex}")
        installSymbolicLink(exe ${linkFileName} ${executableFileName})
    ENDFOREACH()
ENDIF()

# === install the man pages ===
installManPage(libsoxeffect 3)
installManPage(libsoxformat 3)
installManPage(libsox       3)
installManPage(soxeffect    7)
installManPage(soxformat    7)
installManPage(soxi         1)
installManPage(sox          1)
IF(NOT CLP_disableSymlinks)
    # Keep command documentation aligned with the installed dispatch aliases.
    FOREACH(name IN ITEMS play rec play_ng rec_ng)
        _installSymbolicLink("${CLP_installManPath}/man1/${name}.1"
                             "${CLP_installManPath}/man1/sox.1")
    ENDFOREACH()
ENDIF()

# === install the doxygen documentation (if any) ===
IF(Doxygen_FOUND)
    CMAKE_PATH(SET doxygenBuildDirectory NORMALIZE
               ${CMAKE_CURRENT_BINARY_DIR}/doc/html)
    CMAKE_PATH(SET soxDoxygenDirectory NORMALIZE
               "${CLP_installDocPath}/sox_doxygen_doc")
    INSTALL(DIRECTORY ${doxygenBuildDirectory}
            DESTINATION ${soxDoxygenDirectory})
ENDIF()

#------------------------------------------------
# write relevant variables to STDOUT if specified
#------------------------------------------------

IF(CLP_Debug_listBuildVariables)
    LIST(SORT relevantVariableNameList CASE INSENSITIVE)
    UTIL_List_showContents("${relevantVariableNameList}")
ENDIF()
