fn main() {
    slint_build::compile("ui/panel.slint").expect("Slint compilation failed");

    // For embedding Python, we need to link against libpython
    // use_pyo3_cfgs() emits cfg flags for conditional compilation
    pyo3_build_config::use_pyo3_cfgs();

    // Get the interpreter config to emit linker flags
    let config = pyo3_build_config::get();

    // Emit link search path and library for embedding
    if let Some(lib_dir) = &config.lib_dir {
        println!("cargo:rustc-link-search=native={lib_dir}");
        // Add rpath so the binary can find libpython at runtime
        println!("cargo:rustc-link-arg=-Wl,-rpath,{lib_dir}");
    }
    if let Some(lib_name) = &config.lib_name {
        println!("cargo:rustc-link-lib={lib_name}");
    }
}
